#!/usr/bin/env python3
"""Watchdog-safe desk-depth recovery with current same-event groupings.

This wrapper preserves the existing vetted recovery inventory and adds event
aliases discovered by the publication watchdog. It never edits Live items.
"""
import recover_desk_depth as base

# These are two editorial updates of the same Canada/U.S. tariff dispute, not
# two independent World events. Count them once for topic-depth purposes.
base.EVENT_GROUPS.update({
    "world-canada-auto-tariff-20260825": "world-canada-us-tariffs-20260824",
    "world-canada-us-tariffs-20260824-1000": "world-canada-us-tariffs-20260824",
})

if __name__ == "__main__":
    base.main()
