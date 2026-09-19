import json
import os
import unittest
from app.conversational.intent_classifier import classify_intent

class TestDatasetEvaluation(unittest.TestCase):

    def test_evaluate_dataset(self):
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'conversational_prompt_dataset.json')
        
        with open(fixture_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
            
        total = len(dataset)
        correct = 0
        failures = []

        for item in dataset:
            prompt = item['prompt']
            expected = item['expected_classifier_intent']
            
            result = classify_intent(prompt)
            actual = result['intent']
            
            if actual == expected:
                correct += 1
            else:
                failures.append({
                    'id': item['id'],
                    'prompt': prompt,
                    'expected': expected,
                    'actual': actual,
                    'matched_rules': result['matched_rules']
                })
                
        accuracy = (correct / total) * 100 if total > 0 else 0
        
        print("\n--- Dataset Evaluation Results ---")
        print(f"Total evaluated: {total}")
        print(f"Correct: {correct}")
        print(f"Incorrect: {len(failures)}")
        print(f"Accuracy: {accuracy:.2f}%")
        
        if failures:
            print("\nFailures:")
            for f in failures:
                print(f"[{f['id']}] Prompt: '{f['prompt']}'")
                print(f"  Expected: {f['expected']}")
                print(f"  Actual: {f['actual']}")
                print(f"  Matched Rules: {f['matched_rules']}\n")
                
        # We don't fail the unit test if we just want to report accuracy,
        # but to ensure we're aware, we can assert it meets the >= 80% goal.
        self.assertGreaterEqual(accuracy, 80.0, f"Accuracy {accuracy:.2f}% is below the 80% goal.")

if __name__ == '__main__':
    unittest.main()
