"""Gerenciamento de configuração do techlead."""

from pathlib import Path

import yaml

TECHLEAD_DIR = Path.home() / ".techlead"
CONFIG_PATH = TECHLEAD_DIR / "config.yml"
CONTEXT_DIR = TECHLEAD_DIR / "context"
AGENTS_DIR = TECHLEAD_DIR / "agents"


def load_config() -> dict:
    """Carrega a configuração existente ou retorna dict vazio."""
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict) -> None:
    """Salva a configuração em disco."""
    TECHLEAD_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def ensure_dirs() -> None:
    """Garante que a estrutura de diretórios existe."""
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in ["person", "project", "okr", "decision"]:
        (CONTEXT_DIR / subdir).mkdir(exist_ok=True)
