#!/usr/bin/env python3
"""Context engine CLI — memória persistente em .md com decaimento por TTL.

Uso:
    uv run context.py recall [--type TYPE] [--name NAME]
    uv run context.py capture --type TYPE --entity NAME --text "texto"
    uv run context.py decay
"""
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "typer"]
# ///

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import typer
import yaml

app = typer.Typer(help="Context engine para o tech lead.")

TECHLEAD_DIR = Path.home() / ".techlead"
CONTEXT_DIR = TECHLEAD_DIR / "context"
CONFIG_PATH = TECHLEAD_DIR / "config.yml"

EntityType = Literal["person", "project", "okr", "decision"]

DEFAULT_TTL = {
    "person": 30,
    "project": 30,
    "okr": 90,
    "decision": 30,
    "blocker": 7,
}


def _load_config() -> dict:
    """Carrega a configuração existente ou retorna dict vazio."""
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def _entity_path(entity_type: str, name: str) -> Path:
    """Retorna o caminho do arquivo de uma entidade."""
    slug = name.lower().replace(" ", "-")
    return CONTEXT_DIR / entity_type / f"{slug}.md"


def _ttl_days(event_type: str) -> int:
    """Retorna o TTL em dias para um tipo de evento."""
    config = _load_config()
    ttl_config = config.get("ttl", {})
    return ttl_config.get(event_type, DEFAULT_TTL.get(event_type, 30))


def _parse_entity_file(path: Path) -> tuple[dict, list[dict]]:
    """Lê um arquivo de entidade e retorna (frontmatter, eventos)."""
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
            text = block[meta_end + 3 :].strip()
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


@app.command()
def recall(
    entity_type: str | None = typer.Option(None, "--type", "-t", help="Tipo: person, project, okr, decision"),
    name: str | None = typer.Option(None, "--name", "-n", help="Nome da entidade"),
) -> None:
    """Retorna entidades com eventos válidos (não expirados) em JSON."""
    now = datetime.now()
    results = []

    types_to_search = [entity_type] if entity_type else ["person", "project", "okr", "decision"]

    for etype in types_to_search:
        search_dir = CONTEXT_DIR / etype
        if not search_dir.exists():
            continue

        for path in search_dir.glob("*.md"):
            if name and path.stem != name.lower().replace(" ", "-"):
                continue

            frontmatter, events = _parse_entity_file(path)
            valid_events = [e for e in events if datetime.fromisoformat(e["expires_at"]) > now]

            if valid_events or name:
                results.append(
                    {
                        "type": etype,
                        "name": frontmatter.get("name", path.stem),
                        "updated_at": frontmatter.get("updated_at"),
                        "events": valid_events,
                    }
                )

    print(json.dumps(results, ensure_ascii=False, indent=2))


@app.command()
def capture(
    entity_type: str = typer.Option(..., "--type", "-t", help="Tipo: person, project, okr, decision"),
    entity: str = typer.Option(..., "--entity", "-e", help="Nome da entidade"),
    text: str = typer.Option(..., "--text", help="Texto do evento"),
    event_type: str | None = typer.Option(None, "--event-type", help="Tipo do evento (para TTL)"),
) -> None:
    """Salva um evento numa entidade."""
    if not event_type:
        event_type = entity_type

    path = _entity_path(entity_type, entity)
    now = datetime.now()
    expires_at = now + timedelta(days=_ttl_days(event_type))

    if path.exists():
        frontmatter, events = _parse_entity_file(path)
    else:
        frontmatter = {
            "name": entity,
            "type": entity_type,
            "created_at": now.isoformat(timespec="seconds"),
        }
        events = []

    frontmatter["updated_at"] = now.isoformat(timespec="seconds")

    events.append(
        {
            "date": now.isoformat(timespec="seconds"),
            "event_type": event_type,
            "expires_at": expires_at.isoformat(timespec="seconds"),
            "text": text,
        }
    )

    _write_entity_file(path, frontmatter, events)

    result = {
        "status": "ok",
        "path": str(path.relative_to(Path.home())),
        "entity": entity,
        "type": entity_type,
        "total_events": len(events),
    }
    print(json.dumps(result, ensure_ascii=False))


@app.command()
def decay() -> None:
    """Remove eventos expirados de todas as entidades."""
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

    print(json.dumps({"removed": removed}))


@app.command()
def init() -> None:
    """Inicializa a estrutura de diretórios."""
    TECHLEAD_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in ["person", "project", "okr", "decision"]:
        (CONTEXT_DIR / subdir).mkdir(parents=True, exist_ok=True)
    print(json.dumps({"status": "ok", "path": str(TECHLEAD_DIR)}))


if __name__ == "__main__":
    app()
