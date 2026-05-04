"""
Backwards-compat shim. The original keyword-counter implementation has been
superseded by `engine/stance_engine.py` (lexicon-based, multi-dimensional).

Existing call sites that do `from engine.signal_engine import analyze_communication`
keep working — this module re-exports the new implementation. Once all
call sites migrate to importing from `stance_engine` directly, this shim
can be removed.
"""
from __future__ import annotations

from engine.stance_engine import (
    CommunicationSignal,
    analyze_communication,
)

__all__ = ["CommunicationSignal", "analyze_communication"]
