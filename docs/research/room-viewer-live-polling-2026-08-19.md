# Room viewer live-polling failure — research gate

Date: 2026-08-19
Scope: interface / reliability / viewer-network path only

## 1. Observed problem

Direct user screenshots from an already-open `apps/sarah-room.html` / `room/` viewer show:

- retained history loads successfully (`1000 shown · 1000 retained`);
- the status remains on one beat while the displayed age rises for many minutes;
- the source label is `Pages snapshot`;
- reopening the page later reveals a newer beat, proving the Room itself continued advancing while the open viewer did not.

The symptom is therefore not "the Room stopped" and not "history failed to load". The failing invariant is: an already-open viewer can settle on a static Pages artifact and continue presenting it as though its two-second polling loop were a live feed.

## 2. Foundational evidence

This is a browser/network reliability problem rather than a human-behavior mechanism. The relevant foundation is deterministic end-to-end testing of network-dependent UI behavior: isolate each transport, control responses, and assert the UI's state transition rather than infer success from one successful page load.

## 3. Current evidence

Primary/current technical sources consulted 2026-08-19:

- Playwright Network: https://playwright.dev/docs/network — browser-context/page routing can intercept, abort, fulfill, and modify fetch/XHR responses.
- Playwright Mock APIs: https://playwright.dev/docs/mock — API responses can be mocked deterministically without contacting the real service.
- Playwright Browsers: https://playwright.dev/docs/browsers — Playwright supports WebKit and mobile Safari-style device projects for browser regression testing.
- WHATWG Fetch Standard: https://fetch.spec.whatwg.org/ — the CORS-safelisted request-header set is narrow; `Cache-Control` and `Pragma` are not safelisted request headers. Requests with CORS-unsafe request-header names can require a CORS preflight.

This matters because the current viewer adds `Cache-Control` and `Pragma` request headers to every fetch, including cross-origin public GETs to Cloudflare and GitHub Raw. That can turn what should be a simple GET into an OPTIONS preflight dependency. The viewer already uses `cache:'no-store'` plus a unique query parameter, so those custom request headers are not required to create a fresh request.

## 4. Natural-behavior evidence

Not applicable: no human conversational behavior is being changed. The Room's cognition and dialogue engine must remain untouched.

## 5. Mechanism evidence

Two mechanisms exist in the same viewer-network layer:

1. **Request construction:** live public cross-origin reads should remain simple GETs where possible instead of requiring preflight for unnecessary custom request headers.
2. **Source failover:** a static deployment artifact is valid as a boot/history fallback but is not a live transport. When relay/raw are unavailable, the viewer needs a bounded independent fallback whose payload can advance without a Pages redeploy. It must never regress to an older beat.

## 6. Competing explanations

The screenshots could superficially be explained by a frozen Room, slow generation, a stuck JavaScript timer, stale browser cache, or a network outage. The screenshots distinguish these possibilities because reopening later exposes newer beats while the open page's source label remains `Pages snapshot`.

The deterministic baseline also separates source-selection failure from rendering failure: the viewer successfully retained and rendered 1000 messages while repeatedly polling, but stayed at beat 100 because all live paths failed and the independent API path was not consulted.

## 7. Replication / correction / limitations

Playwright WebKit is not branded iOS Safari and cannot reproduce every OS-level networking policy, VPN behavior, or background-tab throttle. Therefore passing the simulator is necessary but not sufficient. Post-deploy validation still requires observing a production page remain open across several real Room beats.

The GitHub REST API is rate-limited, so it must be an emergency/bounded fallback rather than the normal two-second transport.

## 8. Context transfer

The tests run against the actual `room/index.html` viewer code, not a rewritten toy implementation. Network responses alone are simulated. This keeps the test close to production while avoiding dependence on real Cloudflare/GitHub timing during diagnosis.

## 9. Implementation mapping

### Phase A — baseline, completed before production change

A WebKit/iPhone-style Playwright simulator loads the real `room/index.html`, supplies 1000 retained messages, forces Cloudflare relay and GitHub Raw to fail, keeps local Pages `feed.json` fixed at beat 100, exposes an advancing GitHub API source through beats 101–103, and keeps the page open throughout.

Observed baseline diagnostic:

- `pass: false`;
- expected beat 103, observed beat 100;
- status `beat 100 · 308s`;
- meta `1000 shown · 1000 retained · Pages snapshot · auto 2s`;
- relay calls 5;
- raw calls 5;
- API calls 0;
- no page errors.

This reproduces the user's failure while proving the history/render path itself is functioning.

### Phase B — permitted production change

Change **only `room/index.html` viewer-network behavior**:

- remove unnecessary `Cache-Control` / `Pragma` request headers from browser fetches while retaining `cache:'no-store'` and unique query parameters;
- restore a GitHub Contents API fallback with a cooldown so it is not polled every two seconds;
- choose the freshest candidate monotonically;
- never label/accept a stale Pages snapshot as equivalent to a live transport when a fresher independent source exists.

No Room cognition, conversation generation, persistence, Allen injection, or scheduling code is in scope.

## 10. Post-change validation

### Required simulator pass

Without reload:

1. the viewer advances monotonically from beat 100 to at least beat 103;
2. messages from beats 101, 102, and 103 appear in the existing transcript;
3. the 1000-message retained history remains present;
4. a stale Pages snapshot is never accepted over a newer live/API beat;
5. no page exception or unhandled rejection occurs;
6. public cross-origin live reads do not depend on unnecessary preflight-triggering request headers;
7. diagnostic output records source and beat progression.

### Production validation after deployment

Keep the real iPhone viewer open across at least three newly generated Room beats. The visible beat number and transcript must advance without reload. If it does not, the production result overrides simulator success and the viewer change must be revised or reverted.
