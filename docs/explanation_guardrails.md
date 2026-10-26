# Grounded explanation guardrails

SmartAdvisor explanation contract version `1.0` treats engine results as authoritative and renders user-facing explanations from backend-owned templates. The production path is:

`verified engine result -> approved evidence -> guarded deterministic rendering -> ConversationResponse`

The explanation layer does not recalculate compatibility, eligibility, conflicts, or seat availability. It cannot approve an override, register a student, waive prerequisites, guarantee graduation, or invent policy, citations, requirements, or recommendations. Every response carries a deterministic disclaimer establishing those boundaries.

## Approved evidence

Only these derived fields are eligible for an optional explanation-provider payload:

| Result type | Approved engine evidence |
| --- | --- |
| Compatibility | assessment, proposed courses and credits, repeat-course warning, recommendations, data warnings |
| Schedule conflict | conflict state, schedule status, shared days, reason/note, formatted section labels |
| Alternative sections | formatted target and candidates, candidate count, snapshot seat count, timing verification, schedule limitations |
| Clarification/error/escalation/RAG inactive | response code, target handler, and clarification context where applicable |

Student IDs, names, profiles, and academic histories are excluded from the provider payload. Catalog seat counts are labeled as snapshot data and never represented as live registration availability.

For future source-grounded explanations, `ApprovedSourceMetadata` defines a source ID, title, publisher, URL, access time, and content hash. Contract version `1.0` requires the source list to be empty: retrieval and RAG generation remain inactive.

## Templates and limitations

Deterministic templates cover compatibility and backend warnings; confirmed conflict and non-conflict; unknown/TBA timing; alternative candidates and verification limitations; missing or contradictory input; engine errors; advisor escalation; and inactive informational/RAG requests. Unknown timing is explicitly not converted into a no-conflict conclusion. Repeat-course and engine data warnings are preserved.

Required limitations are selected by result type in application code. They include preliminary-guidance and official-advising boundaries, catalog/schedule verification, snapshot-seat wording, unknown-timing cautions, authorized-office requirements, and unavailable engine or RAG states.

## Optional provider seam and fallback

`BaseExplanationProvider` is a provider-independent interface for tests and possible future work. A provider may return only a typed proposal selecting the expected backend template, acknowledging approved evidence reference IDs, and including every required limitation code. It cannot return prose or facts. Extra fields, invented evidence, a mismatched template, missing evidence, or missing limitations fail validation.

When no provider is configured, rendering is deterministic. Provider exceptions or rejected proposals also return the same deterministic explanation without changing the response code, engine result, or parser metadata. The separate fields `explanation_source`, `explanation_fallback_used`, and `explanation_fallback_reason` do not alter the existing parser fallback fields.

Unexpected engine exceptions are represented publicly by generic error text and generic `engine_result.error` values. Raw exception messages, tracebacks, secrets, credential-bearing URLs, and sensitive internal details are not returned by `/conversation`; server logging records only the exception class for these catch paths.

Explanation contract, deterministic templates, and simulated-provider fallback are implemented; live LLM explanation generation is not enabled or verified.
