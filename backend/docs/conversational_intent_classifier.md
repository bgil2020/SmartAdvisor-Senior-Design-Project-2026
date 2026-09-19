# Conversational Intent Classifier

## Purpose and Scope
The conversational intent classifier is a lightweight, framework-independent Python module designed to identify a student's intended action when interacting with SmartAdvisor.

It takes a natural-language prompt as input and returns a structured dictionary representing the classified intent, any matched rule names, and a flag indicating whether the prompt appears to lack necessary entity details (e.g. course codes).

**Important Limitation:** SmartAdvisor is a decision-support tool. The classifier determines the intent of a request but does not make final academic decisions, confirm schedule conflict truths, or guarantee alternative availability. Official advisor review remains required for overrides and critical path decisions.

## Canonical Intents
The classifier maps prompts to one of six canonical intents:
1. `course_compatibility_check`
2. `schedule_conflict_check`
3. `alternative_section_search`
4. `online_override_screening`
5. `unsupported_scope`
6. `clarification`

## Intent Classification vs. Entity Completeness
The classifier's primary responsibility is to determine the *goal* of the request, not its completeness. If a prompt's intent is recognizable but lacks specific details (like specific course codes or section numbers), it will be classified with its actual intent rather than as a generic `clarification`.

To distinguish between a known route needing more info and an unknown route:
- **`intent` (e.g., `course_compatibility_check`) + `needs_clarification=True`**: The intent is clear, but the entity extractor should later prompt the user for the missing details.
- **`intent="clarification"`**: The user's request is ambiguous, multi-intent, or lacks recognizable keywords entirely (e.g., "Can you check my schedule?").

## Rule Precedence
To handle overlapping keywords, the classifier applies rules in this strict precedence order:
1. **Unsupported scope**: Requests for course registration or grade prediction are immediately filtered.
2. **Online override screening**: Explicit phrases such as "online override," "take [course] online," or "eligible for an override" take precedence over general alternative searches.
3. **Alternative-section search**: Explicit requests for another section, different sections, or sections fitting a time constraint take priority over generic conflict keywords.
4. **Schedule conflict check**: Explicit overlap or clash inquiries about selected classes.
5. **Course compatibility check**: Requests evaluating if courses are too hard, risky, or a bad combination to take together.
6. **Clarification**: Default fallback if no clear intent can be safely determined.

Additionally, if a user legitimately combines two distinct requests without a clear primary request (e.g., "Do COP 3530 and MAC 2312 conflict, and if they do, find another COP 3530 section?"), the classifier returns `clarification` because the user should choose one action first.

## Running Tests and Evaluation
The module includes unit tests and an evaluation script against a labeled fixture dataset.

To run the unit test suite:
```bash
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

To run the dataset evaluation and see detailed accuracy metrics:
```bash
PYTHONPATH=backend python3 backend/tests/test_dataset_evaluation.py
```
