import csv
import json
from pathlib import Path

from .models import EmailDraft, Event, Prospect, Recommendation


def read_prospects(path: str | Path) -> list[Prospect]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        return [
            Prospect(
                id=row["id"],
                email=row["email"],
                first_name=row.get("first_name", ""),
                last_name=row.get("last_name", ""),
                company=row.get("company", ""),
                role=row.get("role", ""),
                industry=row.get("industry", ""),
                provider=row.get("provider", "SendGrid"),
                status=row.get("status", "active"),
                last_contacted_day=int(row.get("last_contacted_day", 999)),
            )
            for row in csv.DictReader(file)
        ]


def read_events(path: str | Path) -> list[Event]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        return [
            Event(
                prospect_id=row["prospect_id"],
                event_type=row["event_type"],
                campaign_step=row["campaign_step"],
                day=int(row["day"]),
                hour=int(row["hour"]),
                weekday=int(row.get("weekday", -1) or -1),
            )
            for row in csv.DictReader(file)
        ]


def write_recommendations(path: str | Path, recommendations: list[Recommendation]) -> None:
    rows = [
        {
            "prospect_id": rec.prospect.id,
            "name": f"{rec.prospect.first_name} {rec.prospect.last_name}",
            "company": rec.prospect.company,
            "score": rec.score,
            "segment": rec.segment,
            "next_action": rec.next_action,
            "campaign_step": rec.campaign_step,
            "best_send_weekday": rec.best_send_weekday,
            "best_send_hour": rec.best_send_hour,
            "reason": rec.reason,
        }
        for rec in recommendations
    ]
    _write_csv(path, rows)


def write_email_drafts(path: str | Path, drafts: list[EmailDraft]) -> None:
    rows = [
        {
            "prospect_id": draft.prospect_id,
            "from_email": draft.from_email,
            "template_id": draft.template_id,
            "dynamic_template_data": json.dumps(
                draft.dynamic_template_data, ensure_ascii=False, separators=(",", ":")
            ),
        }
        for draft in drafts
    ]
    _write_csv(path, rows)


def write_dashboard(path: str | Path, dashboard: dict[str, str | int | float]) -> None:
    rows = [{"metric": key, "value": value} for key, value in dashboard.items()]
    _write_csv(path, rows)


def _write_csv(path: str | Path, rows: list[dict[str, object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
