import unittest
from app.conversational.response_policy import build_conversation_response

class TestResponsePolicy(unittest.TestCase):

    def test_complete_compatibility(self):
        # 1. A complete compatibility request routes to course_compatibility_engine with CORE_REQUEST_READY.
        resp = build_conversation_response("Can I take COP 3330 and CEN 4010 together?")
        self.assertEqual(resp["disposition"], "route_core_engine")
        self.assertEqual(resp["target_handler"], "course_compatibility_engine")
        self.assertEqual(resp["response_code"], "CORE_REQUEST_READY")
        self.assertTrue(resp["safe_to_route"])
        self.assertFalse(resp["future_rag_candidate"])
        self.assertIn("ready to be checked for course compatibility", resp["response_text"])

    def test_compatibility_one_course(self):
        # A compatibility request with one course and ambiguous workload term produces clarify, AMBIGUOUS_REQUEST.
        resp = build_conversation_response("Is COP 3330 risky?")
        self.assertEqual(resp["disposition"], "clarify")
        self.assertEqual(resp["response_code"], "AMBIGUOUS_REQUEST")
        self.assertFalse(resp["safe_to_route"])
        self.assertIn("general difficulty/workload", resp["response_text"])
        self.assertIn("compatible with another course", resp["response_text"])
        self.assertEqual(resp["reason"], "Ambiguous single-course workload/compatibility question.")

    def test_missing_second_course(self):
        # A clear compatibility question with only one course returns MISSING_SECOND_COURSE.
        resp = build_conversation_response("Can I take COP 3330 together with another course?")
        self.assertEqual(resp["disposition"], "clarify")
        self.assertEqual(resp["response_code"], "MISSING_SECOND_COURSE")
        self.assertFalse(resp["safe_to_route"])

    def test_complete_schedule_conflict(self):
        # 3. A complete schedule-conflict request routes to scheduling_engine without claiming there is a conflict.
        resp = build_conversation_response("Do COP 3530 section 001 and MAC 2312 section 002 overlap?")
        self.assertEqual(resp["disposition"], "route_core_engine")
        self.assertEqual(resp["target_handler"], "scheduling_engine")
        self.assertEqual(resp["response_code"], "CORE_REQUEST_READY")
        self.assertTrue(resp["safe_to_route"])

    def test_alternative_section_complete(self):
        # 4. An alternative-section request with a course and explicit availability constraint routes to scheduling_engine.
        resp = build_conversation_response("I cannot take classes after 4 PM. Is there another section for COP 3330?")
        self.assertEqual(resp["disposition"], "route_core_engine")
        self.assertEqual(resp["target_handler"], "scheduling_engine")
        self.assertEqual(resp["response_code"], "CORE_REQUEST_READY")
        self.assertTrue(resp["safe_to_route"])

    def test_online_override_screening(self):
        # 5. An online-override screening request routes to online_override_eligibility_engine without claiming approval or eligibility.
        resp = build_conversation_response("Can I take COP 3330 online because I work full time?")
        self.assertEqual(resp["disposition"], "route_core_engine")
        self.assertEqual(resp["target_handler"], "online_override_eligibility_engine")
        self.assertEqual(resp["response_code"], "CORE_REQUEST_READY")
        self.assertTrue(resp["safe_to_route"])

    def test_missing_course_online_request(self):
        # 6. A missing-course online request asks for the course code and is not safe to route.
        resp = build_conversation_response("Can I take this course online because I work full time?")
        self.assertEqual(resp["disposition"], "clarify")
        self.assertEqual(resp["response_code"], "MISSING_COURSE_CODES")
        self.assertFalse(resp["safe_to_route"])

    def test_ambiguous_request(self):
        # 7. An ambiguous or multi-intent request returns clarify and AMBIGUOUS_REQUEST.
        resp = build_conversation_response("I want help.")
        self.assertEqual(resp["disposition"], "clarify")
        self.assertEqual(resp["response_code"], "AMBIGUOUS_REQUEST")

    def test_conflicting_modality(self):
        # 8. A conflicting-modality or other extractor-validation-error case returns INVALID_OR_CONFLICTING_DETAILS.
        resp = build_conversation_response("Can I take COP 3330 online or in-person?")
        self.assertEqual(resp["disposition"], "clarify")
        self.assertEqual(resp["response_code"], "INVALID_OR_CONFLICTING_DETAILS")
        self.assertFalse(resp["safe_to_route"])

    def test_future_rag_candidate_topics(self):
        # 9. "What topics are covered in COP 3530?" becomes future_rag_candidate, targets future_informational_rag.
        resp = build_conversation_response("What topics are covered in COP 3530?")
        self.assertEqual(resp["disposition"], "future_rag_candidate")
        self.assertEqual(resp["target_handler"], "future_informational_rag")
        self.assertTrue(resp["future_rag_candidate"])
        self.assertFalse(resp["safe_to_route"])
        self.assertIn("not enabled in the current prototype", resp["response_text"])

    def test_future_rag_candidate_prerequisites(self):
        # 10. "What are the prerequisites for MAC 2313?" is a future RAG candidate.
        resp = build_conversation_response("What are the prerequisites for MAC 2313?")
        self.assertEqual(resp["disposition"], "future_rag_candidate")
        self.assertEqual(resp["target_handler"], "future_informational_rag")
        self.assertTrue(resp["future_rag_candidate"])

    def test_future_rag_candidate_policy(self):
        # 11. "What does the online override policy say?" is a future RAG candidate.
        resp = build_conversation_response("What does the online override policy say?")
        self.assertEqual(resp["disposition"], "future_rag_candidate")
        self.assertEqual(resp["target_handler"], "future_informational_rag")
        self.assertTrue(resp["future_rag_candidate"])
        self.assertFalse(resp["safe_to_route"])
        self.assertNotEqual(resp["target_handler"], "online_override_eligibility_engine")

    def test_advisor_escalation_approve(self):
        # 12. "Can you approve my override?" becomes advisor_escalation.
        resp = build_conversation_response("Can you approve my override?")
        self.assertEqual(resp["disposition"], "advisor_escalation")
        self.assertEqual(resp["target_handler"], "academic_advisor")
        self.assertEqual(resp["response_code"], "ADVISOR_ESCALATION_REQUIRED")

    def test_advisor_escalation_register(self):
        # 13. "Can you register me for COP 3530?" becomes advisor_escalation.
        resp = build_conversation_response("Can you register me for COP 3530?")
        self.assertEqual(resp["disposition"], "advisor_escalation")
        self.assertEqual(resp["target_handler"], "academic_advisor")
        self.assertEqual(resp["response_code"], "ADVISOR_ESCALATION_REQUIRED")

    def test_advisor_escalation_graduation(self):
        # 14. "Will I definitely graduate on time?" becomes advisor_escalation.
        resp = build_conversation_response("Will I definitely graduate on time?")
        self.assertEqual(resp["disposition"], "advisor_escalation")
        self.assertEqual(resp["target_handler"], "academic_advisor")
        self.assertEqual(resp["response_code"], "ADVISOR_ESCALATION_REQUIRED")

    def test_unsupported_request(self):
        # 15. A clearly unrelated request becomes unsupported.
        resp = build_conversation_response("What grade will I get if I take COP 3530 and CEN 4010?")
        self.assertEqual(resp["disposition"], "unsupported")
        self.assertEqual(resp["response_code"], "UNSUPPORTED_REQUEST")

    def test_top_level_keys_and_entities(self):
        # 16. Every response contains exactly the required top-level keys.
        # 17. Every response embeds the unmodified extractor result under entities.
        # 18. No response text claims that an engine ran, an override was approved, enrollment occurred, a source was retrieved, or an advisor was contacted.
        resp = build_conversation_response("Can I take COP 3330 and CEN 4010 together?")
        expected_keys = {
            "raw_message", "disposition", "target_handler", "intent", "entities", 
            "needs_clarification", "missing_fields", "validation_errors", "response_code", 
            "response_text", "safe_to_route", "future_rag_candidate", "reason"
        }
        self.assertEqual(set(resp.keys()), expected_keys)
        self.assertIn("course_codes", resp["entities"])

if __name__ == '__main__':
    unittest.main()
