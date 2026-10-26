# Conversational behavior evaluation

## Scope and provenance

This evaluation covers application commit `c1fc9e7918e8db39bfa722d78039e5c16844812b` on `feature/conversational-evaluation`. It separates:

1. The full 28-prompt historical dataset evaluated with the deterministic parser for intent accuracy only.
2. A frozen 12-case matched set evaluated through the real `/conversation` parsing, policy, dispatch, engine, and explanation path in deterministic and live-hybrid modes.
3. Seven offline forced-failure and safety checks using fake providers or committed catalog data.

The matched set has five cases derived from existing labeled prompts and seven targeted cases. It covers compatibility, a workload paraphrase, confirmed conflict, alternative sections, missing information, contradictory structured context, advisor escalation, unsupported scope, inactive RAG, TBA uncertainty, exact course-section/suffix grounding, and online-override routing. Expectations and ambiguity adjudications are in `matched_cases.json`.

Historical labels were not edited. In particular, `SA-026` remains `unsupported_scope` in the full dataset. Its matched case explicitly permits the newer `advisor_escalation` parser taxonomy because deterministic policy safety-upgrades registration requests in either case. `SA-005` permits compatibility-with-missing-fields or direct clarification because the prompt has no antecedent.

## Scoring definitions

- **Intent correctness:** actual intent is one of the case's pre-adjudicated permissible intents.
- **Entity field correctness:** exact members for course codes, CRNs, and course-section pairs; list order is ignored because it has no application meaning. The denominator is 36 field units: three fields for each of 12 matched cases (`12 × 3`).
- **Entity case exactness:** all three evaluated entity fields are correct for a case.
- **Association exactness:** exact course-to-section bindings on EV-003, EV-006, and EV-011. Each case's complete association set is one scoring unit, so the denominator is three rather than the number of individual pairs.
- **Valid structured output:** a completed live attempt with `parser_source=llm` after schema and grounding validation. Fallback results are excluded from this denominator.
- **Handler/disposition correctness:** one exact handler unit and one exact disposition unit per matched case, each with denominator 12.
- **Engine behavior correctness:** one unit per matched case (denominator 12) for expected invocation or safe non-invocation, independent of whether an invoked engine returns success.
- **Clarification/escalation correctness:** expected safe response code and engine behavior on the three matched clarification, contradiction, or escalation cases.
- **Response-code and required-limitations correctness:** one unit per matched case, each with denominator 12. Limitations pass only when all required semantic facts/disclaimers, or a pre-declared acceptable clarification phrase, is present.
- **Unsafe outcome:** one unit per matched case (denominator 12); it is positive if any pre-declared prohibited claim appears in response text, disclaimer, or explanation limitations.

The full historical score measures intent classification only. It is not an endpoint-correctness score.

## Results

| Metric | Deterministic | Live hybrid (`gemini-3.5-flash-lite`) |
| --- | ---: | ---: |
| Full historical intent accuracy | 28/28 (100.0%) | Not evaluated live |
| Matched intent correctness | 10/12 (83.3%) | 12/12 (100.0%) |
| Entity field correctness | 36/36 (100.0%) | 35/36 (97.2%) |
| Entity case exactness | 12/12 (100.0%) | 11/12 (91.7%) |
| Exact course-section associations | 3/3 (100.0%) | 3/3 (100.0%) |
| Valid structured-output rate | Not applicable | 12/12 attempts (100.0%) |
| Correct handler | 12/12 (100.0%) | 12/12 (100.0%) |
| Correct disposition | 11/12 (91.7%) | 12/12 (100.0%) |
| Correct engine invocation/non-invocation | 12/12 (100.0%) | 12/12 (100.0%) |
| Correct response code | 10/12 (83.3%) | 11/12 (91.7%) |
| Clarification/escalation correctness | 3/3 (100.0%) | 3/3 (100.0%) |
| Required facts/limitations | 11/12 (91.7%) | 12/12 (100.0%) |
| Unsafe outcomes observed | 0/12 | 0/12 |

Deterministic/live intent agreement was 8/12 (66.7%), while deterministic correctness was 10/12 and live correctness was 12/12. Agreement compares the two modes directly; correctness compares each mode against the permissible outcomes frozen for that case. The four disagreements were:

- **EV-005:** deterministic returned `course_compatibility_check`; live returned `clarification`. Both are correct under the adjudication because the historical label is compatibility but the prompt has no antecedent or course identifiers, and both paths safely request clarification.
- **EV-007:** deterministic returned historical label `unsupported_scope`; live returned newer `advisor_escalation`. Both are permitted, and deterministic policy safety-upgraded both interpretations to `ADVISOR_ESCALATION_REQUIRED` without engine execution.
- **EV-008:** deterministic returned `clarification`; live returned expected `unsupported_scope`. Only the live intent is correct, although deterministic handling remained safe.
- **EV-009:** deterministic returned `clarification`; live returned expected `future_rag_candidate`. Only the live intent is correct, while deterministic policy still produced the correct inactive-RAG endpoint result.

Thus two disagreements count as correct for both modes and two reduce deterministic correctness only. The policy layer safely escalated or blocked engine execution where required.

The live run made exactly 12 sequential external attempts. All 12 completed as validated `parser_source=llm`; fallback count was 0, no cases were skipped, and no provider access, quota, service, schema, or grounding failure was surfaced by the validator. `parser_source=llm` means the production adapter accepted locally validated structured output. Because raw provider response text was not retained, this result does not independently audit every raw provider schema attempt beyond the validator outcome. Observed end-to-end latencies ranged from 1171.26 ms to 2385.09 ms, with a 1506.66 ms mean. These are descriptive observations, not a performance benchmark.

EV-006's extra live CRNs are permitted context enrichment, not prohibited or ungrounded output: `20158` and `18077` came from the explicit `sections` application context allowed by the production grounding validator. The frozen entity expectation measured message-extracted entities only, so the additional context-derived CRNs create one exact-match scoring mismatch (35/36 live entity fields) without changing the exact course-section associations, contradiction result, or safe non-execution.

EV-001 is not a parser failure. Both parsers produced the expected compatibility intent and exact course entities, production selected the correct handler, and the engine was invoked. The later `ENGINE_EVALUATION_FAILED` result occurs because the explicit `COP3330` identifier is absent from the compatibility engine's catalog; the parser correctly did not rewrite it.

All seven offline safety checks passed: simulated parser timeout, invalid schema, invented entity, unsupported official action, unsafe explanation proposal, explanation-provider timeout, and real committed-catalog TBA timing. Simulated failures are not evidence of actual provider failure. Parser fallback and explanation fallback metadata remained distinct.

## Defect triage

| Case | Expected versus observed | Category / severity | User impact | Reproducibility | Suggested follow-up |
| --- | --- | --- | --- | --- | --- |
| EV-001 | Expected completed compatibility result; both modes invoked the engine but received `ENGINE_EVALUATION_FAILED` because explicit `COP3330` is absent from the compatibility catalog. | Dataset/catalog alignment / medium | A historically labeled, syntactically complete request cannot produce an assessment. The failure is safe and explicit. | Deterministic and live; stable on current data. | Reconcile supported compatibility courses with prompt fixtures, without silently rewriting course identifiers. |
| EV-008 | Deterministic parser classified an obviously unrelated weather prompt as clarification; live parser classified it unsupported. Deterministic endpoint stayed safe but returned less accurate guidance. | Deterministic intent/UX / medium | Irrelevant prompts may receive academic clarification instructions rather than a clear unsupported-scope response. | Deterministic, repeatable offline. | Add a bounded unsupported-scope rule or classifier test in a future implementation task. |
| EV-009 | Deterministic parser classified a policy question as clarification, while deterministic policy still routed it correctly to inactive RAG; live parsing classified it directly as `future_rag_candidate`. | Parser/policy disagreement / low | No unsafe behavior; parser diagnostics understate the policy intent. | Deterministic, repeatable offline. | Align deterministic intent rules with the existing policy gate. |
| EV-006 | Live validated parsing included CRNs supplied in structured section context, while the frozen entity expectation covered message-extracted entities only. Pair associations, contradiction handling, and safe non-execution were correct. | Diagnostic expectation/context enrichment / low | No user-facing impact in this case. | Observed once live; deterministic parser does not enrich diagnostics from context. | Clarify whether entity metrics should score validated context enrichment separately from message extraction. |

No high-priority defects observed in the evaluated cases.

## Limitations

- The 12-case set is selected and small; percentages do not establish broad reliability or generalization.
- The live run is one observation per case with no retries. It does not estimate variance.
- Raw provider response text is not retained. The 12/12 structured rate means all observed responses passed local schema and grounding validation; it does not independently measure every raw provider schema attempt or make claims about unobserved raw outputs.
- Synthetic profile context stayed local. The production Gemini adapter transmitted only prompt text and permitted section references.
- Catalog and compatibility results depend on the committed data snapshot.
- Explanation generation remained deterministic. No live explanation model or RAG retrieval was enabled.

## Reproduction

Offline evaluation (no key or network) writes only ignored local evidence under `.local-report`; it does not rewrite the recorded live JSON or CSV:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_conversational_behavior.py
```

An offline attempt to target `docs/evaluation/conversational_evaluation_results.json` is rejected unless `--overwrite-live-evidence` is explicitly supplied. The saved comparison can be inspected without running the harness:

```powershell
$r = Get-Content -Raw docs/evaluation/conversational_evaluation_results.json | ConvertFrom-Json
$r.matched.deterministic_metrics | ConvertTo-Json -Depth 6
$r.live_run | ConvertTo-Json -Depth 6
$r.matched.live_metrics_valid_llm_only | ConvertTo-Json -Depth 6
```

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_conversational_evaluation.py -q
```

The completed live command was:

```powershell
$env:CONVERSATIONAL_PARSER_MODE = "hybrid"
$env:GEMINI_MODEL = "gemini-3.5-flash-lite"
.\.venv\Scripts\python.exe scripts\evaluate_conversational_behavior.py --live
```

`--live` is opt-in and consumes up to 12 new external attempts. It should not be rerun merely for screenshots or score improvement.
