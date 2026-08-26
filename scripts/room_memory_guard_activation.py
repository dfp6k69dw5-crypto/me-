"""Activation stamp for the verified Room memory guard.

This file intentionally contains no runtime behavior. Its user-authored push
lets the permanent Room code-refresh workflow load the already-tested current
main after an Actions-authored source commit, which GitHub does not recursively
trigger from.
"""

MEMORY_GUARD_ACTIVATION = "2026-08-26"
