# Exact-Mapping Syllabus Acquisition Diagnostic Checkpoint

> **No new university request was made for this checkpoint. Automatic syllabus
> acquisition remains access-blocked.** This document separates offline facts,
> hypotheses, and the evidence a single approved instrumented attempt would add.

## Established offline findings

The automatic executor uses Playwright Python 1.64.1 to launch the configured
installed branded Chrome 156 executable. It does not use Playwright's bundled
Chromium headless shell. The API runs the collector as a child with the repository
root as its working directory; the child and browser inherit the process
environment, but the diagnostic recorder captures no environment variables.

Two normal correctness defects were found and fixed:

1. The route handler accessed `request.frame` directly. Playwright documents that
   frame access can throw for service-worker-owned requests and navigation issued
   before a frame exists. Ownership detection now checks service-worker state and
   safely handles unavailable frames.
2. The final URL guard accepted only `/doc/<document-id>/...`, while saved evidence
   shows the normal approved workflow can redirect to
   `/en-US/doc/<document-id>/...`. Both forms are now accepted for the same exact
   tracked document identity.

Neither defect explains the recorded 403: the failed run reached response events
and stopped before final-page validation. The conservative rule that labels an
approved-host `document`, `xhr`, or `fetch` 401/403 as essential remains unchanged.

Playwright also documents that a route handler sees the original request and the
browser follows server redirects without invoking the handler again. The collector
therefore records the response redirect chain and validates the final URL; it does
not claim that the route callback independently approves every redirect hop.

## Sanitized diagnostic contract

Each attempted batch writes one ignored JSON file under
`<syllabus-acquisition-root>/diagnostics/<diagnostic-id>.json`. The API exposes
only `acquisition_diagnostic_id`, not a machine path.

Recorded fields are bounded to 240 events and include:

- local sequential request ID and redirect-parent ID;
- timestamp, method, resource type, navigation flag, and safe ownership category;
- approved host, sanitized endpoint path, query **names only**, and URL fingerprint;
- response status, safe content type, service-worker response flag;
- classifier role and explicit classification reason;
- route action and whether `continue`/`abort` completed;
- sanitized request failures and page errors;
- browser version and non-secret launch-mode facts.

The recorder does not retain headers, cookies, authorization, query values,
fragments, request/response bodies, environment contents, raw HAR, traces, browser
state, source HTML, or local paths. Unknown path segments and error URLs are
fingerprinted locally. Duplicate observation of the same response is ignored so
limits are not double-counted.

## Remaining hypotheses—not causes

The saved historical success was visible with default service-worker behavior;
the automatic attempt was headless with service workers blocked and a route
handler. Timing and source-side behavior also differed. None is established as
the cause. Official Playwright documentation notes that blocking service workers
can change a page that relies on them, while also recommending blocking them when
complete route interception is required. Protections remain in place.

The prior run did not retain the failing endpoint, redirect parent, method,
resource type, ownership, content type, or classification reason. One instrumented
attempt is needed to determine whether the 403 belongs to the tracked document
workflow, an optional approved-host request classified conservatively, or an
unresolved server-side denial.

## Proposed single instrumented attempt

This proposal changes no source identity or browser matrix:

- source: EEL3111 / `202608` / `001` / `a4bh2nqsq`;
- literal tracked `view_url`, including slug and `?mode=view`;
- configured installed Chrome 156, headless child, fresh nonpersistent context;
- service workers blocked and exact navigation/final-URL guards enabled;
- one logical navigation; 20-second browser and 30-second parent deadlines;
- 60 responses total; two failed-essential budget; stop on first essential 401/403;
- no refresh, alternate identity/tool, login, cookies, stealth, HAR, trace, provider
  call, or retry after denial.

Existing project access guidance permits only bounded anonymous navigation to the
tracked public mapping and requires stopping on denial. This checkpoint does not
treat that guidance as approval for the next request; explicit approval is still
required before the one instrumented attempt.

## Official acquisition alternatives reviewed

FAU's [Simple Syllabus guidance](https://www.fau.edu/resources/techtools/canvas/additional-tools/simple-syllabus/)
says a syllabus is public only when its visibility is **General Public**; **Campus
Community** requires FAU SSO. The official publishing guide documents direct share
links and the Syllabus Library. It does not document a public consumer API or a
stable anonymous PDF-download contract.

The saved successful document contains no `doc-pdf` link. Its tracked
`?mode=view&print=true` URL is a print-mode variant of the same browser workflow,
not an independent supported transport. Although search results expose PDF paths
for other public documents, constructing a target-specific vendor endpoint is not
an approved alternative and was not attempted.

Simple Syllabus publicly advertises [institutional LTI, API, and flat-file
integrations](https://simplesyllabus.com/integration/), but no public client API
contract or credentials for this project were found. An institution-supported
export/integration therefore requires coordination with FAU Instructional
Technologies or the platform owner. FAU provides an official
[Simple Syllabus support request](https://helpdesk.fau.edu/TDClient/2061/Portal/Requests/Service/52235/Simple-Syllabus-Support?SIDs=6082).

### Draft support request—not sent

> Subject: Supported anonymous acquisition method for one General Public syllabus
>
> We are an FAU student project testing bounded, anonymous retrieval of the
> published syllabus identified as EEL3111, Fall 2026 term 202608, section 001,
> document `a4bh2nqsq`. A clean Chrome session previously rendered the document,
> while a later unattended clean session stopped on an HTTP 403 classified as a
> document-capable request. The earlier diagnostic did not retain the endpoint;
> an approved instrumented retry would provide its sanitized timestamp, endpoint
> category, method, resource type, and status. No login, cookies, private API,
> bypass, or repeated retries are used. Is this document intended to be General
> Public, and what supported anonymous download/export or institutional integration
> method should this project use? Please also advise on retention and redistribution.

Do not send this draft or open a ticket without separate authorization.
