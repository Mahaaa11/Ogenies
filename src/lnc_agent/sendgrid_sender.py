from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import certifi
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To

from .models import EmailDraft, Prospect


class SendGridSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class SendGridConfig:
    api_key: str


def _api_key_from_env() -> str:
    return os.environ.get("SENDGRID_API_KEY", "").strip()

def _from_email_override() -> str:
    return os.environ.get("LNC_SENDGRID_FROM_EMAIL", "").strip()


def send_dynamic_template_email(
    *,
    cfg: SendGridConfig | None,
    draft: EmailDraft,
    prospect: Prospect,
) -> dict[str, Any]:
    api_key = (cfg.api_key if cfg else "") or _api_key_from_env()
    if not api_key:
        raise SendGridSendError("Missing SENDGRID_API_KEY")
    if not draft.template_id:
        raise SendGridSendError("Missing template_id (set LNC_SENDGRID_TEMPLATE_ID before generating drafts)")
    from_email = _from_email_override() or draft.from_email
    if not from_email:
        raise SendGridSendError("Missing from_email (draft is do_not_contact or invalid)")

    message = Mail(
        from_email=from_email,
        to_emails=To(prospect.email),
    )
    message.template_id = draft.template_id
    message.dynamic_template_data = draft.dynamic_template_data

    # Helpful for webhooks/KPIs if you enable custom_args collection
    try:
        ca: dict[str, str] = {
            "prospect_id": draft.prospect_id,
            "variant": str(draft.dynamic_template_data.get("variant", "")),
        }
        # Optional: allow grouping into mass-send batches ("campagne d'acquisition", J+2, etc.)
        send_batch_id = str(draft.dynamic_template_data.get("send_batch_id", "")).strip()
        if send_batch_id:
            ca["send_batch_id"] = send_batch_id
        campaign_id = str(draft.dynamic_template_data.get("campaign_id", "")).strip()
        if campaign_id:
            ca["campaign_id"] = campaign_id
        message.custom_args = ca
    except Exception:
        pass

    # Fix SSL_CERTIFICATE_VERIFY_FAILED on some macOS/proxy setups
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

    client = SendGridAPIClient(api_key)
    resp = client.send(message)

    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": _safe_body(resp.body),
    }


def _safe_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        try:
            text = body.decode("utf-8", errors="replace")
            try:
                return json.loads(text)
            except Exception:
                return text
        except Exception:
            return "<non-decodable-bytes>"
    return body

