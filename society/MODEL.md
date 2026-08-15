# Society brain

The society is designed so its conversational model is stored by GitHub with this repository rather than supplied by an external inference API.

## Brain asset

- Release tag: `society-brain-v1`
- Asset: `society-brain-q4_0.gguf`
- Model: Qwen2.5-0.5B-Instruct GGUF q4_0
- Parameters: approximately 0.49B
- License: Apache-2.0
- SHA256: `7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed`

The one-time bootstrap workflow copies the model into a Release belonging to `maaronfanberg-lab/me-`. Normal society turns must load the model from that Release only.

## Runtime

The same Release also stores a Linux x64 `llama.cpp` runtime built from pinned commit:

`adb55e5148dc93bcdca7212a2d1df3ccc422959a`

## Permanent state

The entity genomes, learned development, retained memories, shared transcript, and room state are stored under `society/` and committed back to GitHub after successful turns.

GitHub-hosted Actions runners are temporary execution environments. They may hold a copy of the model in memory/disk while a node is thinking, but the persistent copy remains in this GitHub repository's Release.
