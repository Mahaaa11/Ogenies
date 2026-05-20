from collections import defaultdict

from .models import Event, Prospect


PROVIDER_BONUS = {
    "Sender": 8,
    "Brevo": 5,
    "Mailchimp": 4,
}


def group_events_by_prospect(events: list[Event]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.prospect_id].append(event)
    return dict(grouped)


def calculate_interest_score(prospect: Prospect, events: list[Event]) -> tuple[int, list[str]]:
    if prospect.status.lower() == "unsubscribed":
        return 0, ["Prospect unsubscribed"]

    opens = [event for event in events if event.event_type == "open"]
    clicks = [event for event in events if event.event_type == "click"]
    unsubscribes = [event for event in events if event.event_type in ("unsubscribe", "unsubscribed")]
    spam = [event for event in events if event.event_type in ("spamreport", "spam")]
    reasons: list[str] = []
    score = 10

    if opens:
        open_score = min(len(opens) * 12, 30)
        score += open_score
        reasons.append(f"{len(opens)} open(s)")

    if clicks:
        click_score = min(len(clicks) * 22, 45)
        score += click_score
        reasons.append(f"{len(clicks)} click(s)")

    if unsubscribes:
        score -= 60
        reasons.append("unsubscribe event")

    if spam:
        score -= 80
        reasons.append("spam report event")

    if _has_rapid_click(events, window_hours=1):
        score += 12
        reasons.append("rapid click after an open")

    if prospect.provider in PROVIDER_BONUS:
        score += PROVIDER_BONUS[prospect.provider]
        reasons.append(f"{prospect.provider} provider performance")

    if prospect.last_contacted_day <= 2:
        score += 5
        reasons.append("recent activity")

    score = max(0, min(score, 100))
    return score, reasons or ["no engagement yet"]


def _has_rapid_click(events: list[Event], window_hours: int) -> bool:
    opens = [e for e in events if e.event_type == "open"]
    clicks = [e for e in events if e.event_type == "click"]
    if not opens or not clicks:
        return False

    first_open = min(opens, key=lambda e: (e.day, e.hour))
    for click in clicks:
        delta_hours = (click.day - first_open.day) * 24 + (click.hour - first_open.hour)
        if 0 <= delta_hours <= window_hours:
            return True
    return False


def segment_score(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
