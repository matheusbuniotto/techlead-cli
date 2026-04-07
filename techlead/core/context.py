"""Context engine — memória persistente em .md com decaimento por TTL."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml

from techlead.core.config import CONTEXT_DIR, load_config

EntityType = Literal["person", "project", "okr", "decision"]

DEFAULT_TTL = {
    "person": 30,
    "project": 30,
    "okr": 90,
    "decision": 30,
    "blocker": 7,
}

_SEPARATOR = "---\n"


def _entity_path(entity_type: EntityType, name: str) -> Path:
    """Retorna o caminho do arquivo de uma entidade."""
    slug = name.lower().replace(" ", "-")
    return CONTEXT_DIR / entity_type / f"{slug}.md"


def _ttl_days(event_type: str) -> int:
    """Retorna o TTL em dias para um tipo de evento, lendo config se disponível."""
    config = load_config()
    ttl_config = config.get("ttl", {})
    return ttl_config.get(event_type, DEFAULT_TTL.get(event_type, 30))


def _parse_entity_file(path: Path) -> tuple[dict, list[dict]]:
    """
    Lê um arquivo de entidade e retorna (frontmatter, eventos).

    Formato do arquivo:
    ---
    frontmatter yaml
    ---
    ## Histórico
    <!-- event: yaml_inline -->
    Texto do evento
    """
    content = path.read_text(encoding="utf-8")
    parts = content.split("---\n", 2)

    if len(parts) < 3:
        return {}, []

    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2]

    events = []
    for block in body.split("<!-- event:")[1:]:
        try:
            meta_end = block.index("-->")
            meta = yaml.safe_load(block[:meta_end].strip())
            text = block[meta_end + 3:].strip()
            if meta:
                meta["text"] = text
                events.append(meta)
        except (ValueError, yaml.YAMLError):
            continue

    return frontmatter, events


def _write_entity_file(path: Path, frontmatter: dict, events: list[dict]) -> None:
    """Serializa e escreve o arquivo de entidade."""
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["---\n", yaml.dump(frontmatter, allow_unicode=True), "---\n\n## Histórico\n\n"]

    for event in events:
        text = event.pop("text", "")
        meta_yaml = yaml.dump(event, allow_unicode=True, default_flow_style=True).strip()
        event["text"] = text
        lines.append(f"<!-- event: {meta_yaml} -->\n{text}\n\n")

    path.write_text("".join(lines), encoding="utf-8")


def save(entity_type: EntityType, name: str, event_text: str, event_type: str = "") -> None:
    """
    Salva um evento numa entidade.

    Cria a entidade se não existir. Adiciona o evento com expires_at calculado pelo TTL.
    """
    if not event_type:
        event_type = entity_type

    path = _entity_path(entity_type, name)
    now = datetime.now()
    expires_at = now + timedelta(days=_ttl_days(event_type))

    if path.exists():
        frontmatter, events = _parse_entity_file(path)
    else:
        frontmatter = {
            "name": name,
            "type": entity_type,
            "created_at": now.isoformat(timespec="seconds"),
        }
        events = []

    frontmatter["updated_at"] = now.isoformat(timespec="seconds")

    events.append({
        "date": now.isoformat(timespec="seconds"),
        "event_type": event_type,
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "text": event_text,
    })

    _write_entity_file(path, frontmatter, events)


def recall(entity_type: EntityType | None = None, name: str | None = None) -> list[dict]:
    """
    Retorna entidades com seus eventos ainda válidos (não expirados).

    Se entity_type for None, busca em todos os tipos.
    Se name for fornecido, filtra pelo nome da entidade.
    """
    now = datetime.now()
    results = []

    types_to_search: list[EntityType] = (
        [entity_type] if entity_type else ["person", "project", "okr", "decision"]
    )

    for etype in types_to_search:
        search_dir = CONTEXT_DIR / etype
        if not search_dir.exists():
            continue

        for path in search_dir.glob("*.md"):
            if name and path.stem != name.lower().replace(" ", "-"):
                continue

            frontmatter, events = _parse_entity_file(path)
            valid_events = [
                e for e in events
                if datetime.fromisoformat(e["expires_at"]) > now
            ]

            if valid_events or name:
                results.append({
                    "type": etype,
                    "name": frontmatter.get("name", path.stem),
                    "updated_at": frontmatter.get("updated_at"),
                    "events": valid_events,
                })

    return results


def decay() -> int:
    """
    Remove eventos expirados de todas as entidades.

    Retorna o número de eventos removidos.
    """
    now = datetime.now()
    removed = 0

    for etype in ["person", "project", "okr", "decision"]:
        search_dir = CONTEXT_DIR / etype
        if not search_dir.exists():
            continue

        for path in search_dir.glob("*.md"):
            frontmatter, events = _parse_entity_file(path)
            valid = [e for e in events if datetime.fromisoformat(e["expires_at"]) > now]
            expired = len(events) - len(valid)

            if expired > 0:
                removed += expired
                _write_entity_file(path, frontmatter, valid)

    return removed
