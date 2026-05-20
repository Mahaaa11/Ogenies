from .dashboard import build_dashboard
from .decision import choose_next_action
from .email_generator import generate_email_draft
from .models import EmailDraft, Event, Prospect, Recommendation
from .kpi import build_kpis
from .scoring import calculate_interest_score, group_events_by_prospect, segment_score
from .timing import choose_best_send_time


def analyze_campaign(
    prospects: list[Prospect],
    events: list[Event],
) -> tuple[list[Recommendation], list[EmailDraft], dict[str, str | int | float]]:
    events_by_prospect = group_events_by_prospect(events)
    recommendations: list[Recommendation] = []

    for prospect in prospects:
        prospect_events = events_by_prospect.get(prospect.id, [])
        score, reasons = calculate_interest_score(prospect, prospect_events)
        next_action, campaign_step = choose_next_action(prospect, score)
        best_wd, best_hour = choose_best_send_time(prospect_events, default_weekday=1, default_hour=9)
        recommendations.append(
            Recommendation(
                prospect=prospect,
                score=score,
                segment=segment_score(score),
                next_action=next_action,
                campaign_step=campaign_step,
                best_send_weekday=best_wd,
                best_send_hour=best_hour,
                reason=", ".join(reasons),
            )
        )

    email_drafts = [
        generate_email_draft(rec, events_by_prospect.get(rec.prospect.id, []))
        for rec in recommendations
    ]
    dashboard = build_dashboard(recommendations, events)
    dashboard.update(build_kpis(recommendations, events))
    return recommendations, email_drafts, dashboard
