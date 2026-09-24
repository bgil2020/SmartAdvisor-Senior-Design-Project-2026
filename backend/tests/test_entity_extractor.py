import unittest
from app.conversational.entity_extractor import extract_entities

class TestEntityExtractor(unittest.TestCase):
    def test_course_code_normalization(self):
        res = extract_entities("COP3530 and cop-3530 and COP 3530 and MAC 2312")
        self.assertEqual(res["course_codes"], ["COP3530", "MAC2312"])

    def test_compatibility_two_courses(self):
        res = extract_entities("Can I take COP 3330 and CEN 4010 together?")
        self.assertEqual(res["intent"], "course_compatibility_check")
        self.assertEqual(res["course_codes"], ["COP3330", "CEN4010"])
        self.assertFalse(res["needs_clarification"])
        self.assertNotIn("course_codes", res["missing_fields"])

    def test_compatibility_missing_course(self):
        res = extract_entities("Is COP 3330 risky?")
        self.assertEqual(res["intent"], "course_compatibility_check")
        self.assertEqual(res["course_codes"], ["COP3330"])
        self.assertTrue(res["needs_clarification"])
        self.assertIn("course_codes", res["missing_fields"])

    def test_schedule_conflict_time_range(self):
        res = extract_entities("Does COP 3530 Tue/Thu 1-2:15 PM overlap with MAC 2312?")
        self.assertEqual(res["intent"], "schedule_conflict_check")
        self.assertEqual(res["course_codes"], ["COP3530", "MAC2312"])
        ranges = res["schedule_constraints"]["meeting_time_ranges"]
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0]["start_time"], "13:00")
        self.assertEqual(ranges[0]["end_time"], "14:15")
        self.assertIn("TUE", ranges[0]["days"])
        self.assertIn("THU", ranges[0]["days"])
        self.assertFalse(res["needs_clarification"])

    def test_unavailable_after(self):
        res = extract_entities("I cannot attend after 3 PM on Tuesdays and Thursdays. Is there another section for COP 3530?")
        self.assertEqual(res["intent"], "alternative_section_search")
        constraints = res["schedule_constraints"]
        self.assertEqual(constraints["unavailable_after"], "15:00")
        self.assertEqual(constraints["unavailable_days"], ["TUE", "THU"])

    def test_available_before(self):
        res = extract_entities("I am available before 10 AM. Any COP 3530 section?")
        constraints = res["schedule_constraints"]
        self.assertEqual(constraints["available_before"], "10:00")

    def test_modality(self):
        res = extract_entities("Can I take COP 3330 online?")
        self.assertEqual(res["modality_preference"], "online")
        res2 = extract_entities("Can I take COP 3330 in-person?")
        self.assertEqual(res2["modality_preference"], "in_person")
        res3 = extract_entities("Can I take COP 3330 online or in-person?")
        self.assertIsNone(res3["modality_preference"])
        self.assertIn("Conflicting modalities stated.", res3["validation_errors"])

    def test_section_identifiers(self):
        res = extract_entities("Does COP 3530 section 001 overlap with MAC 2312 sec 12345?")
        self.assertEqual(res["section_identifiers"], ["001", "12345"])

if __name__ == '__main__':
    unittest.main()
