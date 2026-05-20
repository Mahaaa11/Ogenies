from __future__ import annotations

from collections import Counter

from .models import Event


def choose_best_send_time(
    events: list[Event],
    default_weekday: int = 1,  # Tuesday
    default_hour: int = 9,
) -> tuple[int, int]:
    """
    Timing optimal (simple heuristic):
    pick the (weekday, hour) slot with the most opens/clicks for this prospect.
    Weekday: 0=Mon ... 6=Sun
    """
    engaged_slots: list[tuple[int, int]] = [
        (e.weekday, e.hour)
        for e in events
        if e.event_type in ("open", "click") and 0 <= e.hour <= 23 and 0 <= e.weekday <= 6
    ]
    if not engaged_slots:
        return int(default_weekday), int(default_hour)
    (wd, hr), _count = Counter(engaged_slots).most_common(1)[0]
    return int(wd), int(hr)


def choose_best_send_hour(events: list[Event], default_hour: int = 9) -> int:
    # Backwards compatible helper: hour only.
    _wd, hr = choose_best_send_time(events, default_weekday=1, default_hour=default_hour)
    return int(hr)

