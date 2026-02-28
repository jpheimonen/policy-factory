"""Heartbeat system — tiered autonomous monitoring for Policy Factory.

The heartbeat is a four-tier escalation chain:
- Tier 1: News skim (cheap, fast — Haiku)
- Tier 2: Triage analysis (mid-tier — Sonnet)
- Tier 3: SA update (capable — Opus)
- Tier 4: Cascade trigger + idea generation

Each tier only fires when the previous tier escalates.
"""

from .orchestrator import run_heartbeat

__all__ = ["run_heartbeat"]
