"""Scheduling services adapter for conversational assistant integration.

Connects conversational requests to existing backend scheduling components:
- Section retrieval (backend.section_retriever)
- Overlap detection (backend.overlap_detector)
- Alternative section search (backend.alternative_section_search)

Implements rigorous section resolution, course suffix preservation,
term consistency checks, and structured result formatting.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .section_retriever import load_course_data
from .overlap_detector import sections_overlap, get_conflict_details
from .meeting_time_normalizer import (
    get_schedule_status,
    is_verified_asynchronous,
    SCHEDULE_STATUS_SCHEDULED,
    SCHEDULE_STATUS_ASYNCHRONOUS,
    SCHEDULE_STATUS_UNKNOWN,
)
from .alternative_section_search import find_alternative_sections

logger = logging.getLogger(__name__)

# Cached courses dataset
_CACHED_COURSES: Optional[pd.DataFrame] = None


def get_course_catalog() -> pd.DataFrame:
    """Load or return cached courses DataFrame from FAU_Courses.xlsx."""
    global _CACHED_COURSES
    if _CACHED_COURSES is None:
        _CACHED_COURSES = load_course_data()
    return _CACHED_COURSES


def normalize_course_code(code: Any) -> str:
    """Normalize course code preserving prefix, number, and suffix (e.g. 'COP 3530C' -> 'COP3530C')."""
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


def format_section_record(sec: pd.Series) -> Dict[str, Any]:
    """Format a pandas section row into a clean JSON-serializable dictionary."""
    beg = str(sec.get("BEG TIME", "")).strip()
    end = str(sec.get("END TIME", "")).strip()
    time_str = f"{beg} - {end}".strip(" -") if beg and end else "Unscheduled / Online"

    sched_status = get_schedule_status(sec)

    return {
        "crn": str(sec["CRN"]).strip().replace(".0", ""),
        "course": str(sec["COURSE"]).strip(),
        "section": str(sec["SECT"]).strip(),
        "title": str(sec.get("TITLE", "")).strip(),
        "days": str(sec.get("DAYS", "")).strip(),
        "time": time_str,
        "method": str(sec.get("METHOD", "")).strip(),
        "campus": str(sec.get("CAMPUS", "")).strip(),
        "term": int(sec["TERM"]) if pd.notna(sec.get("TERM")) else None,
        "seats_remaining": int(sec.get("ENRL REMN", 0)) if pd.notna(sec.get("ENRL REMN")) else 0,
        "instructor": str(sec.get("INSTRUCTOR", "")).strip(),
        "schedule_status": sched_status,
    }


def resolve_section(
    courses: pd.DataFrame,
    identifier: Any,
    term: Optional[int | str] = None,
) -> Tuple[Optional[pd.Series], Optional[str], bool]:
    """Resolve a section input to a single concrete row in the course catalog.

    Accepts:
      - 5-digit CRN string or int (e.g. '20158' or 20158)
      - Dictionary with 'crn' or ('course' and 'section')
      - Object with attributes 'crn' or ('course' and 'section')

    Validates supplied fields against each other to prevent contradictory inputs.

    Returns:
        (section_row, error_message, is_ambiguous)
    """
    if identifier is None:
        return None, "No section identifier provided.", False

    crn_val: Optional[str] = None
    course_val: Optional[str] = None
    sect_val: Optional[str] = None
    item_term: Optional[int | str] = term

    if isinstance(identifier, dict):
        crn_val = identifier.get("crn")
        course_val = identifier.get("course")
        sect_val = identifier.get("section")
        if identifier.get("term") is not None:
            item_term = identifier.get("term")
    elif hasattr(identifier, "crn") or hasattr(identifier, "course"):
        crn_val = getattr(identifier, "crn", None)
        course_val = getattr(identifier, "course", None)
        sect_val = getattr(identifier, "section", None)
        if getattr(identifier, "term", None) is not None:
            item_term = getattr(identifier, "term", None)
    elif isinstance(identifier, (int, str)):
        id_str = str(identifier).strip()
        # Direct CRN (5 digits)
        if id_str.isdigit() and len(id_str) == 5:
            crn_val = id_str
        else:
            # Check if string contains course and section, e.g. "COP 3530C section 001"
            m = re.match(
                r"^([A-Za-z]{3}[\s-]*\d{4}[A-Za-z]?)(?:[\s,]+(?:section|sec|sect)?[\s,]*([0-9A-Za-z]{1,4}))?$",
                id_str,
            )
            if m:
                course_val = m.group(1)
                sect_val = m.group(2)
            else:
                return None, f"Unrecognized section identifier format: '{id_str}'.", False

    # 1. Resolve by CRN if available
    if crn_val:
        crn_clean = str(crn_val).strip().replace(".0", "")
        crn_matches = courses[
            courses["CRN"].fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True) == crn_clean
        ]
        if item_term is not None:
            try:
                term_int = int(item_term)
                crn_matches = crn_matches[crn_matches["TERM"] == term_int]
            except (ValueError, TypeError):
                pass

        if crn_matches.empty:
            return None, f"Section with CRN '{crn_clean}' was not found in the course catalog.", False
        if len(crn_matches) > 1:
            terms = sorted(crn_matches["TERM"].unique())
            return None, f"Multiple sections matched CRN '{crn_clean}' across terms ({terms}). Please specify a term.", True

        sec_match = crn_matches.iloc[0]

        # Validate supplied course/section against the resolved CRN to detect contradictions
        if course_val:
            c_norm = normalize_course_code(course_val)
            cat_c_norm = normalize_course_code(sec_match["COURSE"])
            if c_norm != cat_c_norm:
                return (
                    None,
                    f"Contradictory section details: CRN '{crn_clean}' is course '{sec_match['COURSE']}', "
                    f"which contradicts specified course '{course_val}'.",
                    False,
                )

        if sect_val:
            s_clean = str(sect_val).strip().upper().lstrip("0")
            cat_s_clean = str(sec_match["SECT"]).strip().upper().lstrip("0")
            if s_clean != cat_s_clean:
                return (
                    None,
                    f"Contradictory section details: CRN '{crn_clean}' is section '{sec_match['SECT']}', "
                    f"which contradicts specified section '{sect_val}'.",
                    False,
                )

        return sec_match, None, False

    # 2. Resolve by Course + Section
    if course_val:
        c_norm = normalize_course_code(course_val)
        catalog_courses = courses["COURSE"].fillna("").astype(str).str.strip()
        course_matches = courses[catalog_courses.apply(normalize_course_code) == c_norm]

        if course_matches.empty:
            # Check for possible suffix mismatch without silently equating
            possible = [
                c for c in catalog_courses.unique()
                if normalize_course_code(c).startswith(c_norm) or c_norm.startswith(normalize_course_code(c))
            ]
            hint = f" (Did you mean '{possible[0]}'? Suffixes must match catalog exactly.)" if possible else ""
            return None, f"Course '{course_val}' was not found in the course catalog.{hint}", False

        if not sect_val:
            avail = sorted(course_matches["SECT"].unique())
            return (
                None,
                f"Course '{course_val}' requires a section number. Available sections: {', '.join(avail[:5])}.",
                False,
            )

        sect_clean = str(sect_val).strip().upper()
        sect_padded = sect_clean.zfill(3) if sect_clean.isdigit() else sect_clean

        sect_matches = course_matches[
            course_matches["SECT"].fillna("").astype(str).str.strip().str.upper().isin([sect_clean, sect_padded])
        ]

        if item_term is not None:
            try:
                term_int = int(item_term)
                sect_matches = sect_matches[sect_matches["TERM"] == term_int]
            except (ValueError, TypeError):
                pass

        if sect_matches.empty:
            avail = sorted(course_matches["SECT"].unique())
            return (
                None,
                f"Section '{sect_val}' was not found for course '{course_val}'. Available sections: {', '.join(avail[:5])}.",
                False,
            )

        if len(sect_matches) > 1:
            terms = sorted(sect_matches["TERM"].unique())
            return (
                None,
                f"Multiple sections matched '{course_val}' section '{sect_val}' across terms ({terms}). Please specify a term or CRN.",
                True,
            )

        return sect_matches.iloc[0], None, False

    return None, "Section identifier must specify either a CRN or course and section.", False


def evaluate_schedule_conflict(
    courses: pd.DataFrame,
    section1_input: Any,
    section2_input: Any,
    term: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Evaluates whether two sections have a schedule conflict using overlap_detector.

    Returns a structured dictionary with execution outcome and details.
    Distinguishes scheduled sections, verified asynchronous sections, and unknown/TBA timing.
    """
    sec1, err1, amb1 = resolve_section(courses, section1_input, term)
    if err1:
        return {"success": False, "error": err1, "is_ambiguous": amb1}

    sec2, err2, amb2 = resolve_section(courses, section2_input, term)
    if err2:
        return {"success": False, "error": err2, "is_ambiguous": amb2}

    # Verify term consistency
    if pd.notna(sec1.get("TERM")) and pd.notna(sec2.get("TERM")):
        if int(sec1["TERM"]) != int(sec2["TERM"]):
            return {
                "success": False,
                "error": (
                    f"Cannot check schedule conflict across different terms: "
                    f"{sec1['COURSE']} is in term {sec1['TERM']}, while {sec2['COURSE']} is in term {sec2['TERM']}."
                ),
                "is_ambiguous": False,
            }

    # Execute authoritative overlap functions
    overlap = sections_overlap(sec1, sec2)
    details = get_conflict_details(sec1, sec2)

    s1_formatted = format_section_record(sec1)
    s2_formatted = format_section_record(sec2)

    # If timing is unknown/TBA: Insufficient data must not produce a verified "no conflict"
    if details.get("conflict") == "Unknown":
        return {
            "success": True,
            "has_conflict": None,
            "is_uncertain": True,
            "shared_days": "",
            "conflict_summary": "Unknown",
            "reason": details.get("reason", "Missing or unverified meeting schedule."),
            "schedule_status": "unknown_timing",
            "section_1": s1_formatted,
            "section_2": s2_formatted,
        }

    return {
        "success": True,
        "has_conflict": bool(overlap),
        "is_uncertain": False,
        "shared_days": details.get("shared_days", ""),
        "conflict_summary": details.get("conflict", "No"),
        "note": details.get("note"),
        "schedule_status": details.get("schedule_status"),
        "section_1": s1_formatted,
        "section_2": s2_formatted,
    }


def evaluate_alternative_sections(
    courses: pd.DataFrame,
    target_section_input: Any,
    selected_sections_input: Optional[List[Any]],
    term: Optional[int | str] = None,
    max_results: int = 3,
) -> Dict[str, Any]:
    """Finds non-conflicting open alternative sections using find_alternative_sections.

    Treats an explicitly empty list ([]) as valid zero-enrolled-courses schedule.
    Treats None as missing schedule context.
    Discloses safe limitations if candidate or current schedule timing cannot be verified.
    """
    target_sec, err, amb = resolve_section(courses, target_section_input, term)
    if err:
        return {"success": False, "error": err, "is_ambiguous": amb}

    target_crn = str(target_sec["CRN"]).strip().replace(".0", "")
    target_term = int(target_sec["TERM"]) if pd.notna(target_sec.get("TERM")) else None

    # Handle missing schedule context vs explicitly empty schedule
    if selected_sections_input is None:
        return {
            "success": False,
            "missing_schedule": True,
            "error": "Current schedule is required to find non-conflicting alternative sections.",
            "target_section": format_section_record(target_sec),
        }

    selected_crns: List[str] = []
    resolved_selected: List[Dict[str, Any]] = []
    unknown_sched_sections: List[str] = []

    for item in selected_sections_input:
        s_row, s_err, s_amb = resolve_section(courses, item, term=target_term)
        if s_err:
            return {
                "success": False,
                "error": f"Could not resolve enrolled schedule section: {s_err}",
                "is_ambiguous": s_amb,
            }
        if target_term is not None and pd.notna(s_row.get("TERM")):
            if int(s_row["TERM"]) != target_term:
                return {
                    "success": False,
                    "error": (
                        f"Enrolled section CRN {s_row['CRN']} is in term {s_row['TERM']}, "
                        f"which differs from target section term {target_term}."
                    ),
                    "is_ambiguous": False,
                }

        s_status = get_schedule_status(s_row)
        if s_status == SCHEDULE_STATUS_UNKNOWN:
            unknown_sched_sections.append(f"{s_row['COURSE']} section {s_row['SECT']}")

        crn_str = str(s_row["CRN"]).strip().replace(".0", "")
        selected_crns.append(crn_str)
        resolved_selected.append(format_section_record(s_row))

    try:
        alternatives = find_alternative_sections(
            courses=courses,
            conflicted_crn=target_crn,
            selected_crns=selected_crns,
            max_results=max_results,
        )
    except Exception as exc:
        logger.exception("find_alternative_sections raised an unexpected exception: %s", exc)
        return {
            "success": False,
            "error": "Alternative section search encountered an internal error.",
            "is_engine_error": True,
            "is_ambiguous": False,
        }

    limitations: List[str] = []
    if unknown_sched_sections:
        limitations.append(
            f"Current schedule contains section(s) with unverified or TBA meeting times: "
            f"{', '.join(unknown_sched_sections)}. Cannot guarantee alternative sections avoid conflict with unverified sections."
        )

    alt_records: List[Dict[str, Any]] = []
    for alt in alternatives:
        rec = format_section_record(alt)
        alt_status = get_schedule_status(alt)
        rec["schedule_status"] = alt_status
        if alt_status == SCHEDULE_STATUS_UNKNOWN:
            rec["timing_verified"] = False
            rec["schedule_note"] = "Meeting times unverified or TBA; conflict avoidance cannot be guaranteed."
        else:
            rec["timing_verified"] = True
        alt_records.append(rec)

    has_uncertain_alts = any(not r.get("timing_verified", True) for r in alt_records)
    if has_uncertain_alts:
        limitations.append("One or more alternative sections have unverified or TBA meeting times.")

    return {
        "success": True,
        "target_section": format_section_record(target_sec),
        "selected_schedule": resolved_selected,
        "count": len(alt_records),
        "alternatives": alt_records,
        "selected_crns": selected_crns,
        "has_unknown_schedule": bool(unknown_sched_sections),
        "has_uncertain_alternatives": has_uncertain_alts,
        "limitations": limitations,
    }
