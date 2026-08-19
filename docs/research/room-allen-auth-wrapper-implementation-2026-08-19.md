# Allen auth wrapper implementation delta — 2026-08-19

## Why the implementation mapping changed

The previously planned one-shot GitHub Actions source patch did not publish a repair commit. Rather than keep adding automation around a large, already-working Worker file, the smaller implementation is a new Worker entry module that intercepts only `/api/allen/auth` and `POST /api/allen`, then delegates every other request to the existing `src/index.js` Worker unchanged.

This preserves the evidence-backed mechanism from `room-allen-auth-fallback-2026-08-19.md`: a high-entropy bearer token is checked against a committed SHA-256 verifier, while an existing `ROOM_ALLEN_KEY` remains a compatible first path if Cloudflare exposes it again. The plaintext bearer token is not committed.

## Change boundary

- Add `cloudflare/room-worker/src/index-allen.js`.
- Change only the Wrangler `main` entry from `src/index.js` to `src/index-allen.js`.
- Re-export the existing `RoomState` Durable Object class from the wrapper.
- Delegate all non-Allen requests to the existing Worker.
- Do not alter cognition, Room persistence, feed ordering, viewer behavior, OIDC ingest, or participant identity semantics.

## Pre-deploy simulator

The exact proposed wrapper was executed locally with a stub of the existing Worker boundary. It passed six checks:

1. verifier-backed auth works with no `ROOM_ALLEN_KEY`;
2. wrong key returns 401;
3. missing key returns 401 rather than 503;
4. existing `ROOM_ALLEN_KEY` remains compatible;
5. verifier-backed `POST /api/allen` queues the Allen text;
6. a non-Allen route delegates to the underlying Worker.

## Production validation criteria

After GitHub-to-Cloudflare automatic deployment:

- unauthenticated `/api/allen/auth` must change from `503 allen-key-not-configured` to `401 unauthorized`;
- `/health` must continue to return the existing Room health response;
- only after both checks pass should the new private Allen bearer token be released to the user.
