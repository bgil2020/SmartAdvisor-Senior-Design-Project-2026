# CAP4773 acquisition and generation evidence manifest

This manifest records local evidence through 2026-11-20. It does not authorize
or record any hosted verification. Files marked local-only were deliberately
excluded from commits at the time of this closeout.

## Corrected conclusion

The single-turn diagnostic at `c7b241544a46498f6a99fa508d279ca96085b84c`
verified 11 source relationships, 11 generated-answer relationships, and 11
matches. The table-boundary parser defect was independently reproduced and
fixed offline. This new result does **not** reconstruct either earlier generated
answer: their source/answer relationship comparisons were not retained, so
those earlier outcomes remain inconclusive.

The live two-turn acquisition + Gemini + follow-up-reuse workflow remains
unverified. No result in this manifest should be described as a passing combined
two-turn workflow.

## Artifact inventory

| Artifact | SHA-256 | Tested code / scope | Storage |
|---|---|---|---|
| `cap4773-live-acquisition-2026-11-19.json` | `3B09B19B2AA4C7AFDEDA814824AC0D43C7F0EA498C6DAAB502FDBFC55D21F69F` | `0fca051`; first bounded attempt failed before a complete acceptance result | tracked |
| `cap4773-status-fix-offline-2026-11-19.json` | `4D51100539866DBA6FB4E7F68CEBC13E581C9F8D31ECFDD0664A8F426EF062C3` | `0fca051` plus uncommitted status fix; offline regression only | tracked |
| `cap4773-live-acquisition-next.json` | `3CCE5B498654EAA1347EE927A091365F1C3149BA056797C446D26BF0458EDFF4` | `0fca051` plus uncommitted runtime/harness fixes later checkpointed; fresh acquisition succeeded but the extra harness signature check failed | tracked |
| `cap4773-live-ui-next-redacted.png` | `330D7B6B5A3B814A73506CCCC040A79469C7F84104C5CD58809F0F24F08106FB` | screenshot paired with the preceding attempt | tracked |
| `cap4773-evidence-reuse-offline-2026-11-20.json` | `6218F11DDE3B90E65B9D6EA2FD491ECB6611A973E341C4F200C08C500051A531` | `0fca051` plus uncommitted fixes; offline backend evidence acceptance/reuse | tracked |
| `cap4773-live-acquisition-reuse-next.json` | `0F1908253198191BE0D14BCFBF93F1B475F2D24CA3B6D4181A0CE816AF3EE80B` | changes later checkpointed as `f9a79fb`; live acquisition plus fallback follow-up reuse passed, zero Gemini | tracked |
| `cap4773-live-ui-reuse-next-redacted.png` | `E4A53E3FFC9D6E9F3FDB73A3484534611726FC604452173B24A819BDF7FE431E` | screenshot paired with acquisition/reuse pass | tracked |
| `cap4773-live-acquisition-gemini-reuse-next.json` | `5BB3D3A08B5DEF879D8F611E7D9301E0E3CA7F5345725B6BB4B0158060252DE5` | actual tree `bceb245`; stale embedded `f9a79fb` metadata is corrected separately; first Gemini turn failed the old support gate, no follow-up | tracked |
| `cap4773-live-ui-gemini-reuse-next-redacted.png` | `1CE0494638E9D04A7B1CEE5ADB2A37AD6E3148B258C0C79C7B98E09EA91BE14A` | screenshot paired with the preceding failed combined attempt | tracked |
| `cap4773-combined-test-correction-20261120.md` | `FDB8C921B7FB6915B75352EDC0841BFDCB66B431A2DF6E761B208254DCBA0105` | metadata correction and historical limitations | tracked |
| `cap4773-live-acquisition-gemini-reuse-rerun-next.json` | `CF4092D292C1E5E92B07EE0AB7FEA2E1A183CFDBEE3C38107BBAEFA71B65E140` | `a5441cf`; first Gemini turn had numeric membership but old source relationship count was not retained, no follow-up | local-only |
| `cap4773-live-ui-gemini-reuse-rerun-next-redacted.png` | `BDA3E5B3C6287EE74EB39F2D49D18FF392A31CE8B79A636B9D067CBB71E01279` | screenshot paired with the `a5441cf` rerun | local-only |
| `cap4773-grade-comparison-local-20261120.md` | `71A28400F622BDD604F36C470C283CCBF64F3C584B48D818F5754705404C3E1D` | pre-diagnostic local comparison; source side explicitly unknown | local-only |
| `cap4773-live-grade-relationship-diagnostic-next.json` | `15CAFBA2D788A859472ADDFB3D85265E12FF1D85CFD76F8CCD4A2C494E6ADCFA` | `c7b2415`; single-turn live diagnostic passed 11/11 relationships | local-only |
| `cap4773-live-grade-relationship-diagnostic-next-redacted.png` | `BDA3E5B3C6287EE74EB39F2D49D18FF392A31CE8B79A636B9D067CBB71E01279` | screenshot paired with the `c7b2415` diagnostic | local-only |

## Screenshot provenance finding

The `a5441cf` and `c7b2415` screenshots have the same SHA-256, size, dimensions,
PNG chunk sequence, and bytes. This is expected identical redacted output, not
an incorrect reported hash:

- preflight required the new diagnostic screenshot path not to exist;
- each JSON names its own distinct output path;
- the harness calls Playwright `page.screenshot` directly for the configured
  path and has no copy/reuse path;
- masks cover `.chat-message p`, `.context-grid`, and the composer, removing the
  dynamic content that differed between runs; and
- both images contain only ordinary `IHDR`, `IDAT`, and `IEND` chunks, with no
  timestamp or provenance metadata.

The screenshot therefore corroborates the static redacted UI layout and capture
completion. Its identical pixels cannot independently distinguish the two answer
payloads; the structured JSON is the authoritative answer/relationship evidence.

## Sanitization review

- Every JSON was parsed and recursively checked for raw answer/source/prompt,
  signature-value, credential, and API-key fields; none were present.
- Byte scans found no Google API-key or private-key pattern in any artifact.
- JSON records retain only bounded status, identity, counts, hashes, relationship
  tuples, and signature-presence metadata.
- Screenshots were visually reviewed. Dynamic answer/context areas are masked;
  the visible profile is synthetic test data, not private student data.
- No artifact contains a full syllabus, raw prompt, credential, HMAC signature,
  or private student record.

## Checkpoint boundary

- `c7b241544a46498f6a99fa508d279ca96085b84c`: live single-turn diagnostic pass.
- `7a932fc04cd2d5883848a5d33ea1f03c95c8b2ae`: subsequent production safeguard,
  verified offline only.
