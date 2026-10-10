# SmartAdvisor-Senior-Design-Project-2026
This project is designed to improve the current academic advising and registration process for engineering students at Florida Atlantic University
Course Compatibility Engine

The Course Compatibility Engine evaluates a student's proposed schedule using synthetic student profiles, course information, previous academic workload, and personal circumstances. It provides preliminary recommendations to help students make informed scheduling decisions.

Files Required

Keep these files together in the same folder:

course_compatibility_engine.py — Main Course Compatibility Engine

test_compatability_api.py — Test script for backend integration

Synthetic Profiles.xlsx — Synthetic student profiles

Course Combinations.xlsx — Course-combination data

Final_FAU_CS_CE_EE_Undergraduate_Courses_Revised.xlsx — Course catalog (use the actual filename in the repository)

How to Run

1. Install the required Python package:

py -m pip install openpyxl

2. Run the interactive prototype:

py .\course_compatibility_engine.py

This allows you to select a synthetic student, enter a proposed schedule, and receive personalized recommendations.

3. Run the integration test:

py .\test_compatability_api.py

The test uses a predefined synthetic student and returns structured results, including course compatibility recommendations, completed-course information, and warnings.

To test another student, change the student_id number to a different saved number in the test script.

Integration Notes

The evaluate_compatibility() function in course_compatibility_engine.py can be called by the SmartAdvisor backend without using terminal inputs. It returns a Python dictionary that can be converted to JSON for the frontend.

The engine currently uses synthetic student data and provides preliminary academic planning guidance. It does not replace official academic advising or registration decisions.
