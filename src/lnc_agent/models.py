from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Prospect:
    id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    role: str = ""
    industry: str = ""
    provider: str = "SendGrid"
    status: str = "active"
    last_contacted_day: int = 999


@dataclass(frozen=True)
class Event:
    prospect_id: str
    event_type: str
    campaign_step: str
    day: int
    hour: int
    weekday: int = -1  # 0=Mon ... 6=Sun, derived from timestamp when available


@dataclass(frozen=True)
class Recommendation:
    prospect: Prospect
    score: int
    segment: str
    next_action: str
    campaign_step: str
    best_send_weekday: int
    best_send_hour: int
    reason: str


@dataclass(frozen=True)
class EmailDraft:
    prospect_id: str
    from_email: str
    template_id: str
    dynamic_template_data: dict[str, Any]
