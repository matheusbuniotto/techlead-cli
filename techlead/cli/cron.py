"""Comando interno `tlc _cron` — executado pelo cron job."""

import urllib.request
import urllib.parse
import json

from techlead.core.alerts import filter_new, mark_sent
from techlead.core.config import load_config
from techlead.core.context import decay
from techlead.core.orchestrator import check_criticals


def cron_cmd() -> None:
    """Verifica itens críticos e dispara alertas Slack. Executado pelo cron."""
    config = load_config()
    if not config:
        return

    # Decaimento de contexto
    decay()

    # Verifica críticos
    try:
        alerts = check_criticals()
    except Exception:
        return

    # Filtra alertas já enviados hoje
    new_alerts = filter_new(alerts)
    if not new_alerts:
        return

    # Dispara via Slack webhook
    webhook_url = config.get("slack", {}).get("webhook_url", "")
    if not webhook_url:
        return

    _send_slack_webhook(webhook_url, new_alerts)
    mark_sent(new_alerts)


def _send_slack_webhook(webhook_url: str, alerts: list[str]) -> None:
    """Envia alertas via Slack Incoming Webhook. Sem dependências externas."""
    message = "🦝 *techlead alert*\n\n" + "\n".join(f"• {a}" for a in alerts)
    payload = json.dumps({"text": message}).encode()

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
