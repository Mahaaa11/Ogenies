from .models import Prospect
from .scoring import segment_score


def choose_next_action(prospect: Prospect, score: int) -> tuple[str, str]:
    if prospect.status.lower() == "unsubscribed":
        return "do_not_contact", "none"

    segment = segment_score(score)
    if segment == "high":
        return "personalized_email_and_priority_call", "J+2"
    if segment == "medium":
        return "follow_up_email", "J+2"
    return "nurturing_newsletter", "J+5"
