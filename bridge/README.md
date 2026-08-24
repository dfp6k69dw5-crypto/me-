# Claude bridge

This directory is a GitHub mailbox that lets another connected agent collaborate with Claude without requiring a native Claude connector in that agent's UI.

## How it works

1. A collaborator creates `bridge/inbox/<request-id>.json`.
2. GitHub Actions runs `.github/workflows/claude-bridge.yml`.
3. `bridge/claude_bridge.py` calls Anthropic's Messages API.
4. The workflow commits Claude's answer to `bridge/outbox/<request-id>.json`.
5. Any agent with GitHub read access can read Claude's answer and continue the work.

## Required secret

Add a GitHub Actions repository secret named `ANTHROPIC_API_KEY` containing an Anthropic API key. Never commit the key to the repository.

## Request format

```json
{
  "prompt": "Review the Room stall and identify the safest next operation.",
  "context": [
    "Latest Room beat was at 2026-08-24T16:35:01Z.",
    "Current files of interest: room/conversation.json and .github/workflows/sarah-society.yml"
  ],
  "model": "claude-opus-4-6",
  "max_tokens": 1800
}
```

Only `prompt` is required. `context`, `model`, `max_tokens`, and `system` are optional.

## Security boundary

The workflow sends only the request JSON content to Anthropic. The API key remains in GitHub Actions secrets. Responses are committed to this public repository, so requests must not contain private or secret material.
