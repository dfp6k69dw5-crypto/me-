#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import room_supervisor as supervisor


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def main() -> None:
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)

    healthy_state = {"cycle": 4000, "last_run": iso(now - timedelta(minutes=2))}
    healthy_control = {"last_observed_cycle": 3999, "restart_attempts": 1, "restart_cycle": 3999}
    healthy = supervisor.decide(healthy_state, healthy_control, now=now)
    assert healthy["action"] == "healthy", healthy
    assert healthy["control"]["restart_attempts"] == 0, healthy
    assert healthy["control"]["last_observed_cycle"] == 4000, healthy

    stale_state = {"cycle": 4000, "last_run": iso(now - timedelta(minutes=12))}
    first = supervisor.decide(stale_state, {"last_observed_cycle": 4000}, now=now)
    assert first["action"] == "restart", first
    assert first["control"]["restart_cycle"] == 4000, first
    assert first["control"]["restart_attempts"] == 1, first

    second = supervisor.decide(stale_state, first["control"], now=now + timedelta(minutes=5))
    assert second["action"] == "restart", second
    assert second["control"]["restart_attempts"] == 2, second

    third = supervisor.decide(stale_state, second["control"], now=now + timedelta(minutes=10))
    assert third["action"] == "circuit_open", third
    assert third["control"]["restart_attempts"] == 2, third
    assert third["control"]["circuit_open"] is True, third

    recovered_state = {"cycle": 4001, "last_run": iso(now + timedelta(minutes=11))}
    recovered = supervisor.decide(recovered_state, third["control"], now=now + timedelta(minutes=12))
    assert recovered["action"] == "healthy", recovered
    assert recovered["control"]["circuit_open"] is False, recovered
    assert recovered["control"]["restart_attempts"] == 0, recovered

    print("ROOM SUPERVISOR SIM: GREEN")


if __name__ == "__main__":
    main()
