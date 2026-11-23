from backend.information_sources import approved_information_sources


def test_information_source_inventory_uses_only_exact_tracked_mappings():
    sources = approved_information_sources()
    assert sources["CAP4773"] == ("course_description", "syllabus")
    assert sources["CDA4102"] == ("course_description",)
    assert "MAP3305" not in sources
