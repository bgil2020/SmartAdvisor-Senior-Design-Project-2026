# Weekly RAG v0 Summary

## Contributions

The peer's `test/syllabus-parser` branch culminates at `409ebfb`. Its useful base
is the bounded syllabus adapter and browser circuit breaker in earlier commits
`b90d27b` and `45d55d2`. The final prototype commit adds a manual Playwright demo
and grading-percentage heuristic. It is not in `origin/main` and has no PR.

This branch preserves the bounded adapter commits and adapts the useful heuristic
as optional `extract_grading_categories`, with explicit limits. It does not import
the root `test_browser_collector.py`: that file is a manual network demo, requires
an undeclared Playwright install, opens a visible browser, and is unsuitable for
normal offline discovery. No heuristic output is routed to compatibility,
difficulty, eligibility, or weekly-workload decisions.

The conversational/source integration adds validated local corpus import,
stable chunks, an inspectable lexical retriever, strict applicability filters,
grounded provider/citation validation, excerpt fallback, CLI inspection, and the
smallest change to the established conversation route and response contract.

## Verified

- Baseline `origin/main`: 204 tests passed.
- Syllabus adapter dependency: 219 tests passed after integration.
- Final backend regression after the syllabus-to-RAG follow-up: 236 passed; the
  newly executed syllabus/RAG focused suite passed 31/31. The earlier offline
  forced-failure subset passed 4/4 during the Gemini repair.
- Bounded real catalog collection: 5 requested, 5 fetched/parsed/validated.
- Local corpus after the bounded syllabus demonstration: 6 documents, 19 chunks,
  5 courses, and one EEL3111 Fall 2026 section 001 syllabus.
- Real CLI retrieval: supported, missing-evidence, and ambiguity paths verified.
- Existing API: informational query returns `rag_answered` with structured source.
- Core scheduling/compatibility/advisor routes remain covered by regressions.
- Provider failures retain citations and produce a clearly labeled fallback.
- The prior parser audit's `gemini-3.5-flash-lite` configuration was reconstructed:
  it used `client.models.generate_content`, a process-only `GEMINI_MODEL` override,
  and live structured parsing; explanations remained deterministic.
- The stale `gemini-3.8-flash` shared default was corrected while explicit model
  overrides remain supported.
- RAG response-schema normalization now removes unsupported
  `additionalProperties`, matching the established parser adapter behavior.
- Two real-corpus questions succeeded through a freshly restarted
  `/conversation` server with `generation_source=provider`, model
  `gemini-3.5-flash-lite`, no fallback, and validated source IDs.
- A third live question completed the syllabus-to-RAG chain through
  `/conversation`, citing the real `Course Evaluation Method` chunk for EEL3111
  section 001. Only one of the two allowed generation calls was used.

## Blocked or intentionally not done

- Peer commit `409ebfb` is not merge-ready as written; no peer PR was created or
  merged during this task.
- The first Playwright attempt stopped prematurely because two successful
  initialization responses consumed a failure-oriented essential budget. The
  corrected bounded follow-up established a complete anonymous EEL3111-001
  document in 23 responses without a refresh, denial, login, profile, or cookie.
- Before publication packaging, the new RAG files were uncommitted and unpushed.
  Publication preserves the two selected dependency commits and keeps the feature
  branch unmerged pending team review.

## Next week

1. Confirm long-term redistribution/retention treatment for locally collected
   syllabus text before any content is committed.
2. Add real-data retrieval benchmarks and query synonym/error analysis.
3. Expand the validated corpus deliberately, not via a bulk crawl.
4. Render `rag_sources` in the existing frontend and distinguish generated versus
   excerpt-fallback answers.

## Next-week acquisition backlog

### A. Controlled fetch-on-miss

Acceptance criteria:

- Check local validated evidence before any acquisition.
- Select the source adapter from the informational question type.
- Ask for clarification before fetching when course, term, or section is
  materially ambiguous.
- Permit only bounded approved-source acquisition followed by validation and one
  retrieval retry.
- Store evidence through the existing candidate/acceptance lifecycle; never fetch
  an arbitrary user-supplied URL.
- Return distinct not-found, access-denied, and temporary-failure outcomes.
- Preserve scheduling, compatibility, eligibility, and advisor-escalation
  boundaries.

### B. Reliability for on-demand acquisition

Acceptance criteria:

- Enforce navigation, response, retry, and wall-clock budgets.
- Add negative-result cooldowns without turning temporary failures into permanent
  absence claims.
- Coalesce duplicate requests for the same source identity.
- Keep the last-good validated corpus when acquisition or rebuilding fails.
- Make corpus updates safe under concurrent reads and writes.
- Do not require an unattended visible browser in the serving path.

The supplied scope text ended after the label `C.` with no accompanying task or
acceptance criteria, so no additional backlog item was inferred or implemented.
