"""Activation stamp for verified Room source patches.

This file intentionally contains no runtime behavior. A user-authored update
lets the permanent Room code-refresh workflow load current main after a source
patch committed by GitHub Actions, whose own token does not recursively trigger
new workflows.
"""

ROOM_PATCH_ACTIVATION = "2026-08-26-simplified-refresh"
