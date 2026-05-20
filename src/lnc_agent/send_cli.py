from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import EmailDraft
from .sendgrid_sender import SendGridConfig, send_dynamic_template_email


def read_email_drafts_csv(path: str | Path) -> list[EmailDraft]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        drafts: list[EmailDraft] = []
        for row in csv.DictReader(f):
            drafts.append(
                EmailDraft(
                    prospect_id=row["prospect_id"],
                    from_email=row.get("from_email", ""),
                    template_id=row.get("template_id", ""),
                    dynamic_template_data=json.loads(row.get("dynamic_template_data", "{}") or "{}"),
                )
            )
        return drafts


def send_drafts_via_sendgrid(
    *,
    prospects_csv: str | Path,
    drafts_csv: str | Path,
    api_key: str | None,
    limit: int | None,
    prospect_id: str | None,
    to_email: str | None,
) -> list[dict[str, object]]:
    from .io import read_prospects

    prospects = read_prospects(prospects_csv)
    by_id = {p.id: p for p in prospects}
    drafts = read_email_drafts_csv(drafts_csv)

    cfg = SendGridConfig(api_key=api_key or "")

    results: list[dict[str, object]] = []
    sent = 0
    for d in drafts:
        if limit is not None and sent >= limit:
            break
        if not d.from_email:
            continue
        if prospect_id and d.prospect_id != prospect_id:
            continue
        prospect = by_id.get(d.prospect_id)
        if not prospect:
            results.append({"prospect_id": d.prospect_id, "ok": False, "error": "unknown prospect_id"})
            continue
        if to_email:
            from dataclasses import replace

            prospect = replace(prospect, email=to_email)

        resp = send_dynamic_template_email(cfg=cfg, draft=d, prospect=prospect)
        results.append({"prospect_id": d.prospect_id, "ok": True, "sendgrid": resp})
        sent += 1
    return results

