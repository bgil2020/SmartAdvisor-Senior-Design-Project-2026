# CAP4773 combined-test evidence correction

This note corrects metadata in the original failed combined-test record without
modifying that record or its screenshot.

## Preserved originals

- Diagnostics: `cap4773-live-acquisition-gemini-reuse-next.json`
  - SHA-256: `5BB3D3A08B5DEF879D8F611E7D9301E0E3CA7F5345725B6BB4B0158060252DE5`
- Redacted screenshot: `cap4773-live-ui-gemini-reuse-next-redacted.png`
  - SHA-256: `1CE0494638E9D04A7B1CEE5ADB2A37AD6E3148B258C0C79C7B98E09EA91BE14A`

## Commit metadata correction

The JSON fields `tested_head=f9a79fb...` and
`combined_harness_uncommitted=true` are stale constants, not evidence of a
different executable tree. Commit `f9a79fb` still wrote to the earlier
`cap4773-live-acquisition-reuse-next.json` path and did not contain the combined
Gemini harness. Commit `bceb2451a3e39542ce9ea20504da3e7b7bb4673c`
introduced the combined output path, two-call provider budget, and those stale
metadata constants. The pre-run Git check recorded a clean worktree at
`bceb2451a3e39542ce9ea20504da3e7b7bb4673c`.

Future diagnostics resolve `HEAD` and tracked-diff state from Git instead of
embedding either value in source.

## Numeric-support limitation

The original answer and cited excerpt were intentionally not retained. The
diagnostics contain only support counts and booleans, the screenshot masks the
answer, and the fresh nonpersistent browser context was closed. Therefore the
23-value mismatch cannot be reconstructed as either an unsupported model claim
or a false rejection.

The original checker removed bracketed citation tokens, then extracted unique
number strings from the answer with `\d+(\.\d+)?%?`. It compared that unordered
set against number strings from only the cited academic section, plus the
record's course-number suffix, term, and section. Thus:

- a spaced course identifier such as `CAP 4773` was counted in the answer;
- bracketed citation IDs were not counted;
- duplicate numbers and range direction/order were discarded;
- range endpoints were counted separately;
- percent signs and decimal spellings were compared literally, so `90`, `90%`,
  and `90.0%` were different values; and
- grade/category labels were discarded, so numbers could be associated with
  the wrong label without detection.

Code review did identify independent checker defects: numeric values were
compared as literal strings, and an unordered set comparison discarded
grade/category associations. Those defects are corrected and covered by
offline regression tests. This correction does not change the failed result or
claim that the combined workflow passed.
