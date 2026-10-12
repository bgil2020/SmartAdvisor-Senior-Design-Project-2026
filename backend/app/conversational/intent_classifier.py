import re
from typing import Dict, Any

# Canonical intent names
COURSE_COMPATIBILITY = "course_compatibility_check"
SCHEDULE_CONFLICT = "schedule_conflict_check"
ALTERNATIVE_SECTION = "alternative_section_search"
ONLINE_OVERRIDE = "online_override_screening"
CLARIFICATION = "clarification"
UNSUPPORTED_SCOPE = "unsupported_scope"

# Rule precedence: Unsupported > Online Override > Alternative Section > Schedule Conflict > Course Compatibility
# These are grouped by intent in order of priority.
RULES = [
    (UNSUPPORTED_SCOPE, [
        (r'\bregister\b', "unsupported:registration"),
        (r'\bwhat grade will i get\b', "unsupported:grade_prediction"),
        (r'\bpredict (my )?grade\b', "unsupported:grade_prediction"),
        (r'\bgrade prediction\b', "unsupported:grade_prediction"),
        (r'\bwill i get (an? )?[a-f]\b', "unsupported:grade_prediction"),
    ]),
    (ONLINE_OVERRIDE, [
        (r'\bonline override\b', "override:explicit"),
        (r'\btake[^\.\?]*online\b', "override:take_online"),
        (r'\beligible[^\.\?]*override\b', "override:eligible"),
        (r'\boverride[^\.\?]*questions\b', "override:questions"),
    ]),
    (ALTERNATIVE_SECTION, [
        (r'\b(?:another|different|alternative)\s+section[s]?\b', "alternative:another_section"),
        (r'\banother[^\.\?]*section\b', "alternative:another_section"),
        (r'\bdifferent[^\.\?]*section\b', "alternative:different_section"),
        (r'\balternative[^\.\?]*section[s]?\b', "alternative:alternative_section"),
        (r'\balternative\b', "alternative:keyword"),
        (r'\bwhat else can i take\b', "alternative:what_else"),
        (r'\bwhat else can i take instead\b', "alternative:what_else_instead"),
        (r'\bfits around\b', "alternative:fits_around"),
        (r'\bonline section[s]?\b', "alternative:online_section"),
        (r'\bbetter class\b', "alternative:better_class"),
        (r'\bcannot take[^\.\?]*after\b', "alternative:time_constraint"),
    ]),
    (SCHEDULE_CONFLICT, [
        (r'\boverlap[s]?\b', "conflict:overlap"),
        (r'\bconflict[s]?\b', "conflict:keyword"),
        (r'\bclash\b', "conflict:clash"),
        (r'\bsame time\b', "conflict:same_time"),
        (r'\bcollide\b', "conflict:collide"),
    ]),
    (COURSE_COMPATIBILITY, [
        (r'\btogether\b', "compatibility:together"),
        (r'\btoo much\b', "compatibility:too_much"),
        (r'\brisky\b', "compatibility:risky"),
        (r'\bbad combo\b', "compatibility:bad_combo"),
        (r'\bworkload\b', "compatibility:workload"),
        (r'\btoo hard\b', "compatibility:too_hard"),
    ])
]

def count_course_codes(text: str) -> int:
    """Extract course codes like 'COP 3530' or 'COP3530' to estimate completeness."""
    matches = re.findall(r'\b[a-z]{3}\s*\d{4}\b', text)
    return len(set(matches))

def classify_intent(prompt: str) -> Dict[str, Any]:
    if not prompt or not prompt.strip():
        return {
            "intent": CLARIFICATION,
            "matched_rules": [],
            "needs_clarification": True,
            "reason": "The request is empty."
        }

    normalized = prompt.strip().lower()
    
    # Check for specific multi-intent phrasing without a clear primary request
    # "Do X and Y conflict, and if they do, find another..."
    if re.search(r'\bconflict[s]?\b.*\band\s+(if|find|also)\b', normalized):
        if re.search(r'\banother|\balternative|\bdifferent', normalized):
            return {
                "intent": CLARIFICATION,
                "matched_rules": ["multi_intent:conflict_and_alternative"],
                "needs_clarification": True,
                "reason": "Multiple intents detected. Please separate your requests."
            }
            
    # Gather all matched intents and their specific rules
    matched_intents = {}
    
    for intent, patterns in RULES:
        for pattern, rule_name in patterns:
            if re.search(pattern, normalized):
                if intent not in matched_intents:
                    matched_intents[intent] = []
                matched_intents[intent].append(rule_name)

    # Apply precedence
    selected_intent = None
    selected_rules = []
    
    for intent, _ in RULES:
        if intent in matched_intents:
            selected_intent = intent
            selected_rules = matched_intents[intent]
            break

    # If no intent matched, it's a clarification
    if not selected_intent:
        return {
            "intent": CLARIFICATION,
            "matched_rules": [],
            "needs_clarification": True,
            "reason": "The request does not clearly identify a supported SmartAdvisor action."
        }

    # Handle unsupported scope
    if selected_intent == UNSUPPORTED_SCOPE:
        return {
            "intent": UNSUPPORTED_SCOPE,
            "matched_rules": selected_rules,
            "needs_clarification": False,
            "reason": "Course registration and grade prediction are outside the SmartAdvisor prototype scope."
        }

    # Determine if clarification is needed based on missing course codes
    needs_clarification = False
    course_count = count_course_codes(normalized)
    
    if selected_intent in [COURSE_COMPATIBILITY, SCHEDULE_CONFLICT]:
        if course_count < 2:
            needs_clarification = True
    elif selected_intent in [ALTERNATIVE_SECTION, ONLINE_OVERRIDE]:
        if course_count < 1:
            needs_clarification = True

    return {
        "intent": selected_intent,
        "matched_rules": selected_rules,
        "needs_clarification": needs_clarification,
        "reason": None
    }
