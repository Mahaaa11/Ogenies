from .models import Event, Recommendation


def build_dashboard(recommendations: list[Recommendation], events: list[Event]) -> dict[str, str | int | float]:
    total = len(recommendations)
    opens = sum(1 for event in events if event.event_type == "open")
    clicks = sum(1 for event in events if event.event_type == "click")
    unsubscribes = sum(1 for event in events if event.event_type in ("unsubscribe", "unsubscribed"))
    spam = sum(1 for event in events if event.event_type in ("spamreport", "spam"))
    high_score = sum(1 for rec in recommendations if rec.segment == "high")
    medium_score = sum(1 for rec in recommendations if rec.segment == "medium")
    low_score = sum(1 for rec in recommendations if rec.segment == "low")

    return {
        "total_prospects": total,
        "total_opens": opens,
        "total_clicks": clicks,
        "total_unsubscribes": unsubscribes,
        "total_spam_reports": spam,
        "open_rate_events_per_prospect": round(opens / total, 2) if total else 0,
        "click_rate_events_per_prospect": round(clicks / total, 2) if total else 0,
        "high_interest_prospects": high_score,
        "medium_interest_prospects": medium_score,
        "low_interest_prospects": low_score,
    }
