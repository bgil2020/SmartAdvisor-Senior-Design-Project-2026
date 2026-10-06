from backend.section_retriever import load_course_data, get_section_by_crn
from backend.alternative_section_search import find_alternative_sections
from backend.result_formatter import build_alternative_response, print_alternatives


def main():
    print("=" * 65)
    print("SMARTADVISOR BACKEND")
    print("Alternative Section Search")
    print("=" * 65)

    try:
        courses = load_course_data()
    except Exception as error:
        print(f"\nCould not load FAU course data: {error}")
        return

    print(f"\nLoaded {len(courses)} FAU course-section records.")

    print("\nEnter all CRNs currently in the student's schedule.")
    print("Example: 16817, 19129, 21920")
    selected_input = input("Selected CRNs: ").strip()

    selected_crns = [
        crn.strip()
        for crn in selected_input.split(",")
        if crn.strip()
    ]

    conflicted_crn = input(
        "CRN that needs an alternative: "
    ).strip()

    conflicted_section = get_section_by_crn(courses, conflicted_crn)

    if conflicted_section is None:
        print(f"\nCRN {conflicted_crn} was not found in the spreadsheet.")
        return

    try:
        alternatives = find_alternative_sections(
            courses=courses,
            conflicted_crn=conflicted_crn,
            selected_crns=selected_crns,
            max_results=3,
        )
    except ValueError as error:
        print(f"\n{error}")
        return

    response = build_alternative_response(
        conflicted_section,
        alternatives,
    )

    print_alternatives(response)


if __name__ == "__main__":
    main()
