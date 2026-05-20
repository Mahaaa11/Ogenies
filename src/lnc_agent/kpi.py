from __future__ import annotations

from .models import Event, Recommendation


def build_kpis(recommendations: list[Recommendation], events: list[Event]) -> dict[str, int | float]:
    total_prospects = len(recommendations)

    opens = sum(1 for e in events if e.event_type == "open")
    clicks = sum(1 for e in events if e.event_type == "click")
    unsubscribes = sum(1 for e in events if e.event_type in ("unsubscribe", "unsubscribed"))
    spam = sum(1 for e in events if e.event_type in ("spamreport", "spam"))

    avg_score = round(sum(r.score for r in recommendations) / total_prospects, 2) if total_prospects else 0.0

    hot = sum(1 for r in recommendations if r.score >= 70)
    warm = sum(1 for r in recommendations if 30 <= r.score < 70)
    cold = sum(1 for r in recommendations if r.score < 30)

    def pct(n: int) -> float:
        return round((n / total_prospects) * 100, 2) if total_prospects else 0.0

    return {
        "total_prospects": total_prospects,
        "open_events": opens,
        "click_events": clicks,
        "unsubscribe_events": unsubscribes,
        "spam_events": spam,
        "open_rate_events_per_prospect": round(opens / total_prospects, 2) if total_prospects else 0.0,
        "click_rate_events_per_prospect": round(clicks / total_prospects, 2) if total_prospects else 0.0,
        "unsubscribe_rate_pct": pct(unsubscribes),
        "spam_rate_pct": pct(spam),
        "avg_interest_score": avg_score,
        "hot_score_pct": pct(hot),
        "warm_score_pct": pct(warm),
        "cold_score_pct": pct(cold),
    }

