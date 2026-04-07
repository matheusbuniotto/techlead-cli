"""Testes do módulo core/config."""

import pytest
import yaml

from techlead.core.config import ensure_dirs, load_config, save_config


def test_load_config_arquivo_inexistente(tmp_path, monkeypatch):
    """load_config retorna dict vazio se config não existe."""
    monkeypatch.setattr("techlead.core.config.CONFIG_PATH", tmp_path / "config.yml")
    assert load_config() == {}


def test_save_e_load_config(tmp_path, monkeypatch):
    """save_config persiste e load_config recupera corretamente."""
    config_path = tmp_path / "config.yml"
    techlead_dir = tmp_path

    monkeypatch.setattr("techlead.core.config.CONFIG_PATH", config_path)
    monkeypatch.setattr("techlead.core.config.TECHLEAD_DIR", techlead_dir)

    config = {"slack": {"user_id": "U123"}, "ttl": {"blocker": 7}}
    save_config(config)

    loaded = load_config()
    assert loaded["slack"]["user_id"] == "U123"
    assert loaded["ttl"]["blocker"] == 7


def test_ensure_dirs_cria_estrutura(tmp_path, monkeypatch):
    """ensure_dirs cria todos os subdiretórios necessários."""
    context_dir = tmp_path / "context"
    agents_dir = tmp_path / "agents"

    monkeypatch.setattr("techlead.core.config.CONTEXT_DIR", context_dir)
    monkeypatch.setattr("techlead.core.config.AGENTS_DIR", agents_dir)

    ensure_dirs()

    assert context_dir.exists()
    assert agents_dir.exists()
    for subdir in ["person", "project", "okr", "decision"]:
        assert (context_dir / subdir).exists()
