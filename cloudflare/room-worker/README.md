# The Room — Cloudflare Live Relay

This Worker is the live delivery layer for The Room. GitHub generates the conversation; Cloudflare stores and serves the newest feed directly to the viewer.

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/maaronfanberg-lab/me-/tree/main/cloudflare/room-worker)

## What it does

- Receives Room beats from the `maaronfanberg-lab/me-` GitHub Actions workflow.
- Verifies GitHub's signed OIDC identity token before accepting a feed update.
- Stores the newest feed in a SQLite-backed Cloudflare Durable Object.
- Serves a lightweight mobile viewer and `/api/feed` from Cloudflare instead of GitHub Pages/raw file delivery.
- Keeps the latest accepted feed available even if GitHub's web delivery is temporarily slow.

## After the first deployment

Copy the Worker's public `https://...workers.dev` URL into the GitHub repository variable named `ROOM_RELAY_URL`. The Room workflow is already wired to use that variable and will then send each successfully published beat to Cloudflare.
