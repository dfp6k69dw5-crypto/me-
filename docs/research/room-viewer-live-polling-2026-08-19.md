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

Primary/current tool documentation consulted 2026-08-19:

- Playwright Network: https://playwright.dev/docs/network — browser-context/page routing can intercept, abort, fulfill, and modify fetch/XHR responses.
- Playwright Mock APIs: https://playwright.dev/docs/mock — API responses can be mocked deterministically without contacting the real service.
- Playwright Browsers: https://playwright.dev/docs/browsers — Playwright supports WebKit and mobile Safari-style device projects for browser regression testing.

These capabilities map directly to the observed failure because the simulator can make Cloudflare and GitHub Raw fail while keeping a static Pages snapshot available and independently advancing a GitHub API source.

## 4. Natural-behavior evidence

Not applicable: no human conversational behavior is being changed. The Room's cognition and dialogue engine must remain untouched.

## 5. Mechanism evidence

The current viewer has multiple read paths. A static deployment artifact is valid as a boot/history fallback but is not a live transport. The mechanism to validate is source freshness and failover: when a live transport is unavailable, the viewer must use another transport whose payload can advance independently of the deployed HTML artifact; it must never regress to an older beat.

## 6. Competing explanations

The screenshots could superficially be explained by a frozen Room, slow generation, a stuck JavaScript timer, stale browser cache, or a network outage. The screenshots distinguish these possibilities because reopening later exposes newer beats while the open page's source label remains `Pages snapshot`. The simulator must still cover timer continuity and source failures so a future regression cannot hide behind a different cause.

## 7. Replication / correction / limitations

Playwright WebKit is not branded iOS Safari and cannot reproduce every OS-level networking policy, VPN behavior, or background-tab throttle. Therefore passing the simulator is necessary but not sufficient. Post-deploy validation still requires observing a production page remain open across several real Room beats.

## 8. Context transfer

The test will run against the actual `room/index.html` viewer code, not a rewritten toy implementation. Network responses alone are simulated. This keeps the test close to production while avoiding dependence on the real Cloudflare/GitHub timing during diagnosis.

## 9. Implementation mapping

Phase A — baseline only, no production viewer change:

- add a WebKit/iPhone-style Playwright simulator;
- load the real `room/index.html`;
- provide 1000 retained history messages;
- force Cloudflare relay and GitHub Raw to fail;
- keep local Pages `feed.json` fixed at beat 100;
- expose a GitHub API feed that advances through beats 101, 102, 103;
- keep the page open throughout.

Only after that simulator fails on the current viewer may the viewer's source-selection/failover layer be changed. No cognition, conversation, persistence, or workflow-generation code may be changed for this bug.

## 10. Post-change validation

### Pre-change baseline expected failure

Within an already-open simulated viewer:

- history count reaches at least 1000;
- current code remains at beat 100 / `Pages snapshot`;
- the simulator records that the available advancing API source was never consumed.

### Required post-change pass

Without reload:

1. the viewer advances monotonically from beat 100 to at least beat 103;
2. messages from beats 101, 102, and 103 appear in the existing transcript;
3. the 1000-message retained history remains present;
4. a stale Pages snapshot is never accepted over a newer live/API beat;
5. no page exception or unhandled rejection occurs;
6. the diagnostic output records the observed source and beat sequence.

### Production validation after deployment

Keep the real iPhone viewer open across at least three newly generated Room beats. The visible beat number and transcript must advance without reload. If it does not, the production result overrides simulator success and the viewer change must be revised or reverted.
