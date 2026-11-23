# Automatic syllabus discovery

SmartAdvisor can optionally resolve a selected course, term, and section through
FAU's rendered public Simple Syllabus library when no tracked exact mapping is
available. This is an opt-in extension of the existing headed-browser acquisition
path, not an unrestricted crawler.

## Runtime contract

Enable both source acquisition and discovery:

```text
SYLLABUS_ACQUISITION_ENABLED=true
SYLLABUS_AUTO_DISCOVERY_ENABLED=true
ACQUISITION_BROWSER_MODE=headed
```

Optional bounds are `SYLLABUS_DISCOVERY_TIMEOUT_SECONDS` (default 20),
`SYLLABUS_DISCOVERY_MAX_RESPONSES` (default 60), and
`SYLLABUS_DISCOVERY_MAX_RENDERED_HTML_BYTES` (default 2 MiB). Existing
`ACQUISITION_TEST_SYLLABUS_BUDGET` accounting is claimed before discovery; one
token covers the library search and selected document acquisition together.

The resolver searches with the selected course and section, accepts only links
on `fau.simplesyllabus.com`, and filters links by exact course, semester/year,
and section. If multiple rendered links have the same exact identity, it chooses
the first result in rendered order and records the match count and selection
strategy. The selected document still has to pass the existing rendered-content,
identity, provenance, and citation validation before it can support an answer.

The resolver fails closed for missing terms, no exact match, access denial,
response/size exhaustion, browser errors, incomplete documents, and identity
mismatch. It does not construct document IDs, use private endpoints, switch to a
different section, sign in, retry automatically, or retain raw syllabus HTML.

## Existing tracked mappings

Tracked mappings remain preferred and avoid a discovery navigation:

- CAP4773 / 202608 / 001 / `fjhz2vvga`
- COP4331 / 202608 / 002 / `sb4d8l8wb`
- EEL3111 / 202608 / 001 / `a4bh2nqsq`

Automatic discovery is verified offline with rendered synthetic library results.
A bounded live validation is still required before enabling it in a hosted demo.
