import re
from typing import Dict, Any, List, Optional
from app.conversational.intent_classifier import (
    classify_intent,
    COURSE_COMPATIBILITY,
    SCHEDULE_CONFLICT,
    ALTERNATIVE_SECTION,
    ONLINE_OVERRIDE,
    CLARIFICATION,
    UNSUPPORTED_SCOPE
)

def normalize_day(day_str: str) -> str:
    mapping = {
        'm': 'MON', 'mon': 'MON', 'monday': 'MON',
        't': 'TUE', 'tue': 'TUE', 'tuesday': 'TUE', 'tu': 'TUE',
        'w': 'WED', 'wed': 'WED', 'wednesday': 'WED',
        'th': 'THU', 'thu': 'THU', 'thursday': 'THU',
        'f': 'FRI', 'fri': 'FRI', 'friday': 'FRI',
        'sat': 'SAT', 'saturday': 'SAT',
        'sun': 'SUN', 'sunday': 'SUN',
    }
    return mapping.get(day_str.lower(), '')

def extract_all_days(text: str) -> List[str]:
    text_lower = text.lower()
    days = []
    
    if re.search(r'\bmwf\b', text_lower):
        days.extend(['MON', 'WED', 'FRI'])
    if re.search(r'\btth\b', text_lower) or re.search(r'\bt/th\b', text_lower) or re.search(r'\btue/thu\b', text_lower):
        days.extend(['TUE', 'THU'])
        
    day_pattern = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)s?\b'
    for m in re.finditer(day_pattern, text_lower):
        d = normalize_day(m.group(1))
        if d:
            days.append(d)
            
    res = []
    seen = set()
    for d in days:
        if d not in seen:
            seen.add(d)
            res.append(d)
    return res

def parse_time(time_str: str, ampm: str = None) -> Optional[str]:
    if not time_str: return None
    time_str = time_str.strip()
    parts = time_str.split(':')
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if ampm:
        ampm = ampm.lower()
        if 'p' in ampm and h < 12:
            h += 12
        if 'a' in ampm and h == 12:
            h = 0
    return f"{h:02d}:{m:02d}"

def extract_course_codes(text: str) -> List[str]:
    matches = re.findall(r'\b([a-zA-Z]{3})[\s-]*(\d{4})\b', text)
    codes = []
    seen = set()
    for prefix, num in matches:
        code = f"{prefix.upper()}{num}"
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes

def extract_section_identifiers(text: str) -> List[str]:
    matches = re.findall(r'\b(?:section|sec)\s+(\d+)\b', text, re.IGNORECASE)
    secs = []
    seen = set()
    for m in matches:
        if m not in seen:
            seen.add(m)
            secs.append(m)
    return secs

def extract_schedule_constraints(text: str) -> dict:
    constraints = {
        "available_days": [],
        "unavailable_days": [],
        "available_before": None,
        "available_after": None,
        "unavailable_before": None,
        "unavailable_after": None,
        "meeting_time_ranges": []
    }
    
    days_rx = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)s?\b'
    unavail_rx = r'\b(cannot\s+attend|cannot\s+take|unavailable|no\s+classes)[\s\w]{0,30}?(?:on\s+)?((?:' + days_rx + r'(?:\s+(?:and|,)\s+)?)+)'
    avail_rx = r'\b(available|can\s+attend|can\s+take)[\s\w]{0,30}?(?:on\s+)?((?:' + days_rx + r'(?:\s+(?:and|,)\s+)?)+)'

    explicit_days_text = ""
    
    for m in re.finditer(unavail_rx, text, re.IGNORECASE):
        days_chunk = m.group(2)
        days = extract_all_days(days_chunk)
        for d in days:
            if d not in constraints["unavailable_days"]:
                constraints["unavailable_days"].append(d)
        explicit_days_text += " " + days_chunk

    for m in re.finditer(avail_rx, text, re.IGNORECASE):
        days_chunk = m.group(2)
        days = extract_all_days(days_chunk)
        for d in days:
            if d not in constraints["available_days"]:
                constraints["available_days"].append(d)
        explicit_days_text += " " + days_chunk
        
    explicit_days_set = set(extract_all_days(explicit_days_text))
    
    before_after_rx = r'\b(cannot\s+attend|cannot\s+take|unavailable|no\s+classes|available|can\s+attend|free)[\s\w]{0,20}?(before|after)\s*(\d{1,2}(?::\d{2})?)\s*([ap]\.?m\.?)?'
    for m in re.finditer(before_after_rx, text, re.IGNORECASE):
        context = (m.group(1) or '').lower()
        direction = m.group(2).lower()
        time_str_raw = m.group(3)
        ampm_raw = m.group(4)
        
        time_val = parse_time(time_str_raw, ampm_raw)
        if time_val:
            is_negative = bool(re.search(r'(cannot|unavailable|no)', context))
            if direction == 'before':
                if is_negative: constraints["unavailable_before"] = time_val
                elif 'available' in context or 'can ' in context or 'free' in context: constraints["available_before"] = time_val
            else:
                if is_negative: constraints["unavailable_after"] = time_val
                elif 'available' in context or 'can ' in context or 'free' in context: constraints["available_after"] = time_val

    time_rx = r'(\d{1,2}(?::\d{2})?)\s*([ap]\.?m\.?)?'
    range_rx = f'{time_rx}\\s*(?:to|-)\\s*{time_rx}\\s*([ap]\\.?m\\.?)?'
    
    for m in re.finditer(range_rx, text, re.IGNORECASE):
        start_t, start_ampm, end_t, end_ampm, overall_ampm = m.groups()
        s_ampm = start_ampm or overall_ampm
        e_ampm = end_ampm or overall_ampm
        
        # Propagate end ampm to start if missing, e.g. "1-2:15 PM"
        if not s_ampm and e_ampm:
            s_ampm = e_ampm
            
        start_24 = parse_time(start_t, s_ampm)
        end_24 = parse_time(end_t, e_ampm)
        
        all_days = extract_all_days(text)
        days_for_range = [d for d in all_days if d not in explicit_days_set]
        unique_days = []
        for d in days_for_range:
            if d not in unique_days:
                unique_days.append(d)
                
        constraints["meeting_time_ranges"].append({
            "days": unique_days,
            "start_time": start_24,
            "end_time": end_24
        })
        
    return constraints

def extract_modality(text: str, validation_errors: list) -> Optional[str]:
    text_lower = text.lower()
    is_online = bool(re.search(r'\b(online|remote|virtual)\b', text_lower))
    is_in_person = bool(re.search(r'\b(in[\s-]?person|on\s*campus|face[\s-]?to[\s-]?face)\b', text_lower))
    is_hybrid = bool(re.search(r'\b(hybrid|blended)\b', text_lower))
    
    modes = sum([is_online, is_in_person, is_hybrid])
    if modes > 1:
        validation_errors.append("Conflicting modalities stated.")
        return None
    
    if is_online: return "online"
    if is_in_person: return "in_person"
    if is_hybrid: return "hybrid"
    return None

def extract_entities(message: str) -> dict:
    cls_res = classify_intent(message)
    intent = cls_res["intent"]
    matched_rules = cls_res["matched_rules"]
    needs_clarification = cls_res["needs_clarification"]
    reason = cls_res["reason"]
    
    validation_errors = []
    course_codes = extract_course_codes(message)
    section_identifiers = extract_section_identifiers(message)
    schedule_constraints = extract_schedule_constraints(message)
    modality_preference = extract_modality(message, validation_errors)
    
    missing_fields = []
    
    course_count = len(course_codes)
    if intent in [COURSE_COMPATIBILITY, SCHEDULE_CONFLICT]:
        if course_count < 2:
            needs_clarification = True
            missing_fields.append("course_codes")
        else:
            needs_clarification = False
    elif intent in [ALTERNATIVE_SECTION, ONLINE_OVERRIDE]:
        if course_count < 1:
            needs_clarification = True
            missing_fields.append("course_codes")
        else:
            needs_clarification = False

    if intent == SCHEDULE_CONFLICT:
        if course_count >= 2 and not section_identifiers and not schedule_constraints["meeting_time_ranges"]:
            missing_fields.append("section_identifiers")
            needs_clarification = True

    return {
        "raw_message": message,
        "intent": intent,
        "matched_rules": matched_rules,
        "needs_clarification": needs_clarification,
        "reason": reason,
        "course_codes": course_codes,
        "section_identifiers": section_identifiers,
        "schedule_constraints": schedule_constraints,
        "modality_preference": modality_preference,
        "missing_fields": sorted(list(set(missing_fields))),
        "validation_errors": validation_errors
    }
