# Offline Syllabus Parser Feasibility Comparison

> **Saved-data experiment only. No university request or provider call was made.**
> This comparison does not change the existing Playwright acquisition pipeline,
> access-denial behavior, or source contract.

## Inputs and boundary

The real-data input was the previously saved complete rendered EEL3111 Fall 2026
section 001 HTML. That artifact existed only because the earlier bounded browser
session completed. Its validated candidate was the comparison reference.

No separate real initial/static HTML response was saved. The failed instrumented
run retained sanitized lifecycle diagnostics, not response bodies. The repository's
`library_shell.html` is a synthetic test fixture and is not presented as real-source
evidence. No applicable local PDF exists.

## Executed comparison

| Method | Input artifact | Acquisition already required? | Full academic content? | Identity/locators | Validation | Differences | New dependency | Replaces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Existing `_RenderedParser` (`html.parser`) | Historical complete rendered HTML | Yes | Yes: 13/13 reference sections | Exact | Passed | Exact document text and content hash | No | Extraction only; current implementation |
| Beautiful Soup 4.12.2 with `html.parser` | Historical complete rendered HTML | Yes | Yes: 13/13 sections; assessment exact | Exact | Passed | 10/13 normalized-text exact; whitespace changed in instructor, integrity, and grading-scale sections; content hash changed | Yes in the active Python 3.12 environment | Extraction only |
| Beautiful Soup | Synthetic library-shell fixture | Not real source evidence | No: zero academic sections | None | Not applicable | JavaScript shell only | Same as above | Neither |
| `lxml` / `html5lib` | Not executed | — | Unknown | Unknown | Not run | Packages are not installed; no specific unresolved extraction defect justifies adding them | Would be required | Not established |
| Recorded `?mode=view&print=true` link | Manifest metadata only | Would use the same document workflow | Not evaluated | Same mapped identity | Not run | No evidence it is a standalone downloadable PDF | No parser dependency | Not established |
| Public PDF/export | No applicable artifact or approved link | — | Unknown | Unknown | Not run | Saved rendered HTML contains no `doc-pdf` link | Unknown | Not established |

The Beautiful Soup experiment used the repository validator and wrote a separate
ignored candidate. It preserved course, term, section, document ID, trusted source
URL, 13 heading locators, and the assessment passage. Navigation markers were
absent. Instructor information remained in the authoritative candidate, while the
existing corpus rules excluded that section and three repeated institutional
boilerplate sections from retrieval, yielding the same nine usable chunks.

Beautiful Soup's grading-scale output inserted boundaries between table-derived
cells that the current parser concatenates. That can improve readability, but it
also changes exact source text and content identity. It did not improve the already
exact assessment passage and does not justify silently changing the established
candidate/hash contract.

## Interpretation

**Beautiful Soup is useful for extraction after browser acquisition; this does
not replace the blocked acquisition step.** It is not installed in the project's
active Python 3.12 environment, although version 4.12.2 was available in a separate
Python 3.11 installation with the standard `html.parser` builder. No package was
installed for this experiment.

The existing parser remains the smallest compatible choice: it has no external
dependency and exactly reproduces the validated record. If table readability
becomes a concrete requirement, add a narrow synthetic table fixture and improve
the existing block-boundary handling without changing unrelated sections. Do not
replace source acquisition or refetch denied content to evaluate that change.

The recorded print-mode URL is not evidence of an independent PDF transport, and
no endpoint was guessed or requested. The official-source review remains documented
in [Exact-Mapping Syllabus Acquisition Diagnostic Checkpoint](rag-syllabus-diagnostics.md).

## Verdict

**A — an alternative parser can improve some table whitespace after acquisition,
but acquisition remains blocked.** Keep the production parser and Playwright
safeguards unchanged. The smallest next step is no acquisition change; optionally
prototype table-aware whitespace only if the team adopts a specific readability
acceptance test.
