from __future__ import annotations

from backend.syllabi.discovery import discover_exact_syllabus, exact_syllabus_candidates, term_name_from_id


LIBRARY_HTML = """
<main>
  <a href="/doc/wrongterm/Spring-2026-MAP-3305-003-Engineering-Math?mode=view">MAP 3305 003</a>
  <a href="/doc/wrongsection/Fall-2026-1-Full-Term-MAP-3305-004-Engineering-Math?mode=view">MAP 3305 004</a>
  <a href="https://evil.example/doc/notallowed/Fall-2026-MAP-3305-003">MAP 3305 003</a>
  <a href="/en-US/doc/firstdoc/Fall-2026-1-Full-Term-MAP-3305-003-Engineering-Math">View MAP 3305 003</a>
  <a href="/doc/seconddoc/Fall-2026-MAP-3305-003-Engineering-Math?mode=view">Another MAP 3305 003</a>
</main>
"""


def test_term_id_converts_to_user_facing_semester_and_year():
    assert term_name_from_id("202601") == "Spring 2026"
    assert term_name_from_id("202605") == "Summer 2026"
    assert term_name_from_id("202608") == "Fall 2026"
    assert term_name_from_id("Fall 2026") is None


def test_exact_candidates_reject_wrong_term_section_and_host():
    candidates = exact_syllabus_candidates(
        LIBRARY_HTML,
        course_code="MAP 3305",
        term_id="202608",
        section="003",
    )

    assert [candidate["source_document_id"] for candidate in candidates] == ["firstdoc", "seconddoc"]
    assert candidates[0]["term_name"] == "Fall 2026"
    assert candidates[0]["view_url"].startswith("https://fau.simplesyllabus.com/en-US/doc/firstdoc/")
    assert candidates[0]["view_url"].endswith("?mode=view")


def test_course_code_and_section_are_distinct_identity_tokens():
    html = """
    <a href="/doc/a/Fall-2026-MAP-33050-003-Wrong-Course">wrong course</a>
    <a href="/doc/b/Fall-2026-MAP-3305-1003-Wrong-Section">wrong section</a>
    """
    assert exact_syllabus_candidates(html, course_code="MAP3305", term_id="202608", section="003") == []


class FakeSession:
    instances: list["FakeSession"] = []

    def __init__(self, *, visible, limits):
        self.visible = visible
        self.limits = limits
        self.closed = False
        self.query = None
        self.__class__.instances.append(self)

    def search(self, query):
        self.query = query
        return {
            "status": "rendered",
            "html": LIBRARY_HTML,
            "logical_navigations": 1,
            "actual_observed_responses": 8,
            "rendered_html_bytes": len(LIBRARY_HTML),
        }

    def close(self):
        self.closed = True


def test_discovery_selects_first_exact_match_and_cleans_up(monkeypatch):
    FakeSession.instances.clear()
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "true")

    result = discover_exact_syllabus("MAP3305", "202608", "003", session_factory=FakeSession)

    assert result["status"] == "exact_source_selected"
    assert result["exact_match_count"] == 2
    assert result["selection_strategy"] == "first_exact_course_term_section_match"
    assert result["mapping"]["source_document_id"] == "firstdoc"
    assert FakeSession.instances[0].query == "MAP3305 003"
    assert FakeSession.instances[0].closed is True


def test_discovery_disabled_makes_no_browser_session(monkeypatch):
    FakeSession.instances.clear()
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "false")

    result = discover_exact_syllabus("MAP3305", "202608", "003", session_factory=FakeSession)

    assert result == {"status": "disabled", "mapping": None, "logical_navigations": 0}
    assert FakeSession.instances == []


def test_discovery_error_is_sanitized_and_cleanup_still_runs(monkeypatch):
    class BrokenSession(FakeSession):
        def search(self, query):
            raise RuntimeError("raw browser detail")

    BrokenSession.instances.clear()
    monkeypatch.setenv("SYLLABUS_AUTO_DISCOVERY_ENABLED", "true")

    result = discover_exact_syllabus("MAP3305", "202608", "003", session_factory=BrokenSession)

    assert result["status"] == "discovery_error"
    assert result["error_type"] == "RuntimeError"
    assert "raw browser detail" not in str(result)
    assert BrokenSession.instances[0].closed is True
