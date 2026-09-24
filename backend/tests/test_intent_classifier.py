import unittest
from app.conversational.intent_classifier import (
    classify_intent,
    COURSE_COMPATIBILITY,
    SCHEDULE_CONFLICT,
    ALTERNATIVE_SECTION,
    ONLINE_OVERRIDE,
    CLARIFICATION,
    UNSUPPORTED_SCOPE
)

class TestIntentClassifier(unittest.TestCase):

    def test_course_compatibility(self):
        # Positive cases
        self.assertEqual(classify_intent("Can I take COP 3330 and CEN 4010 together?")["intent"], COURSE_COMPATIBILITY)
        self.assertEqual(classify_intent("Is COP3530 and CEN4010 a bad combo?")["intent"], COURSE_COMPATIBILITY)
        self.assertEqual(classify_intent("Is the workload for COP 3530 and MAC 2312 too much?")["intent"], COURSE_COMPATIBILITY)

    def test_schedule_conflict(self):
        self.assertEqual(classify_intent("Do COP 3530 and MAC 2312 overlap?")["intent"], SCHEDULE_CONFLICT)
        self.assertEqual(classify_intent("Will COP 3530 conflict with CEN 4010?")["intent"], SCHEDULE_CONFLICT)
        self.assertEqual(classify_intent("Do these two classes clash?")["intent"], SCHEDULE_CONFLICT)

    def test_alternative_section(self):
        self.assertEqual(classify_intent("Find me another section of COP 3530.")["intent"], ALTERNATIVE_SECTION)
        self.assertEqual(classify_intent("Are there online sections of COP 3530?")["intent"], ALTERNATIVE_SECTION)
        self.assertEqual(classify_intent("I cannot take classes after 4 PM.")["intent"], ALTERNATIVE_SECTION)
        self.assertEqual(classify_intent("COP 3530 is full. What else can I take instead this semester?")["intent"], ALTERNATIVE_SECTION)

        # Ambiguous alternative wording
        res = classify_intent("Can you find me a better class?")
        self.assertEqual(res["intent"], ALTERNATIVE_SECTION)
        self.assertTrue(res["needs_clarification"])

    def test_instead_false_positives(self):
        # Generic "instead" must not automatically become alternative
        res = classify_intent("Should I meet with an advisor instead?")
        self.assertEqual(res["intent"], CLARIFICATION)

    def test_online_override(self):
        self.assertEqual(classify_intent("Can I take this course online because I work full time?")["intent"], ONLINE_OVERRIDE)
        self.assertEqual(classify_intent("Am I eligible for an override?")["intent"], ONLINE_OVERRIDE)
        self.assertEqual(classify_intent("I have an online override question.")["intent"], ONLINE_OVERRIDE)

    def test_unsupported_scope(self):
        self.assertEqual(classify_intent("Can you register me for COP 3530?")["intent"], UNSUPPORTED_SCOPE)
        self.assertEqual(classify_intent("What grade will I get if I take COP 3530 and CEN 4010?")["intent"], UNSUPPORTED_SCOPE)

    def test_grade_false_positives(self):
        # Uses of “grade” that are not grade prediction
        self.assertNotEqual(classify_intent("Does this course have a grade requirement?")["intent"], UNSUPPORTED_SCOPE)

    def test_clarification_cases(self):
        self.assertEqual(classify_intent("Can you check my schedule?")["intent"], CLARIFICATION)
        self.assertEqual(classify_intent("I want help with COP 3530.")["intent"], CLARIFICATION)

    def test_edge_cases(self):
        # Empty and None
        self.assertEqual(classify_intent("")["intent"], CLARIFICATION)
        self.assertEqual(classify_intent("   ")["intent"], CLARIFICATION)
        self.assertEqual(classify_intent(None)["intent"], CLARIFICATION)

        # Casing and punctuation
        self.assertEqual(classify_intent("cAn I TAkE cOp 3330 aND cEn 4010 tOgEtHEr???")["intent"], COURSE_COMPATIBILITY)

    def test_needs_clarification_distinction(self):
        # Intent clear, but missing details
        res1 = classify_intent("Are these classes too hard to take together?")
        self.assertEqual(res1["intent"], COURSE_COMPATIBILITY)
        self.assertTrue(res1["needs_clarification"])

        res2 = classify_intent("Can I get an online override?")
        self.assertEqual(res2["intent"], ONLINE_OVERRIDE)
        self.assertTrue(res2["needs_clarification"])

        res3 = classify_intent("Does my Algorithms section overlap with Calculus?")
        self.assertEqual(res3["intent"], SCHEDULE_CONFLICT)
        self.assertTrue(res3["needs_clarification"])

        # Intent unclear
        res4 = classify_intent("Can you check my schedule?")
        self.assertEqual(res4["intent"], CLARIFICATION)
        self.assertTrue(res4["needs_clarification"])

        res5 = classify_intent("I want help with COP 3530.")
        self.assertEqual(res5["intent"], CLARIFICATION)
        self.assertTrue(res5["needs_clarification"])

    def test_multi_intent_request(self):
        # Both conflict and alternative
        res = classify_intent("Do COP 3530 and MAC 2312 conflict, and if they do, find another COP 3530 section?")
        self.assertEqual(res["intent"], CLARIFICATION)
        self.assertTrue("Multiple intents" in res["reason"])

    def test_informational_queries_and_lexical_limitations(self):
        """
        This test captures current raw regex-classifier behavior for regression purposes.
        The raw classifier's `online_override_screening` output for a general policy-information 
        question is a known lexical limitation due to keyword matching.
        The response-policy layer is responsible for overriding this case into the 
        informational future-RAG path.
        """
        prompts = [
            "What topics are covered in COP 3530?",
            "What are the prerequisites for MAC 2313?",
            "What does the online override policy say?"
        ]
        
        for prompt in prompts:
            res = classify_intent(prompt)
            if prompt == "What does the online override policy say?":
                # Known lexical limitation: raw mapping matches keywords. 
                # This is overridden by the response policy.
                self.assertEqual(
                    res["intent"], 
                    ONLINE_OVERRIDE, 
                    "Raw classifier matches keywords instead of recognizing general policy intent"
                )
            else:
                self.assertNotIn(res["intent"], [
                    COURSE_COMPATIBILITY,
                    SCHEDULE_CONFLICT,
                    ALTERNATIVE_SECTION,
                    ONLINE_OVERRIDE
                ])
                self.assertIn(res["intent"], [CLARIFICATION, UNSUPPORTED_SCOPE])

    def test_risky_raw_behavior(self):
        res = classify_intent("Is COP 3330 risky?")
        self.assertNotIn(res["intent"], [
            SCHEDULE_CONFLICT,
            ALTERNATIVE_SECTION,
            ONLINE_OVERRIDE
        ])
        self.assertEqual(res["intent"], COURSE_COMPATIBILITY)

if __name__ == '__main__':
    unittest.main()
