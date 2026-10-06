from backend.overlap_detector import (
    sections_overlap,
    has_schedule_information,
    get_conflict_details,
)


def test_overlapping_sections():
    section1 = {
        "DAYS": "MWF",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    section2 = {
        "DAYS": "MWF",
        "BEG TIME": "10:30 AM",
        "END TIME": "11:30 AM",
        "METHOD": "In-Person",
    }

    assert sections_overlap(section1, section2) is True


def test_non_overlapping_sections():
    section1 = {
        "DAYS": "MWF",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    section2 = {
        "DAYS": "MWF",
        "BEG TIME": "11:00 AM",
        "END TIME": "12:00 PM",
        "METHOD": "In-Person",
    }

    assert sections_overlap(section1, section2) is False


def test_no_shared_days():
    section1 = {
        "DAYS": "MWF",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    section2 = {
        "DAYS": "TR",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    assert sections_overlap(section1, section2) is False


def test_online_section():
    section1 = {
        "DAYS": "",
        "BEG TIME": None,
        "END TIME": None,
        "METHOD": "Distance Learning",
    }

    section2 = {
        "DAYS": "MWF",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    assert sections_overlap(section1, section2) is False


def test_missing_time():
    section = {
        "DAYS": "MWF",
        "BEG TIME": None,
        "END TIME": None,
        "METHOD": "In-Person",
    }

    assert has_schedule_information(section) is False


def test_conflict_details():
    section1 = {
        "DAYS": "MWF",
        "BEG TIME": "10:00 AM",
        "END TIME": "11:00 AM",
        "METHOD": "In-Person",
    }

    section2 = {
        "DAYS": "MW",
        "BEG TIME": "10:30 AM",
        "END TIME": "11:30 AM",
        "METHOD": "In-Person",
    }

    result = get_conflict_details(section1, section2)

    assert result["conflict"] == "Yes"
    assert result["shared_days"] == "M, W"