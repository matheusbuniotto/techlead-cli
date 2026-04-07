"""Testes dos comandos manuais."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import techlead.core.context as ctx
from techlead.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_context(tmp_path, monkeypatch):
    """Isola o context engine em tmp_path."""
    context_dir = tmp_path / "context"
    for sub in ["person", "project", "okr", "decision"]:
        (context_dir / sub).mkdir(parents=True)
    monkeypatch.setattr(ctx, "CONTEXT_DIR", context_dir)


@pytest.fixture
def mock_config(monkeypatch):
    """Mock de config válida."""
    monkeypatch.setattr(
        "techlead.cli.commands.load_config",
        lambda: {"slack": {"token": "xoxb-test", "user_id": "U123"}},
    )


def test_capture_salva_na_memoria(mock_config):
    """capture classifica e salva o texto no context engine."""
    classificacao = json.dumps({
        "entity_type": "person",
        "entity_name": "João",
        "event_type": "blocker",
    })

    with patch("techlead.cli.commands._invoke_claude", return_value=classificacao):
        result = runner.invoke(app, ["capture", "João está bloqueado na PROJ-42"])

    assert result.exit_code == 0
    assert "Capturado" in result.output

    entities = ctx.recall("person", "João")
    assert len(entities) == 1
    assert "João está bloqueado na PROJ-42" in entities[0]["events"][0]["text"]


def test_capture_fallback_sem_json(mock_config):
    """capture usa fallback decision/geral se LLM não retornar JSON válido."""
    with patch("techlead.cli.commands._invoke_claude", return_value="resposta inválida"):
        result = runner.invoke(app, ["capture", "Decisão importante sobre arquitetura"])

    assert result.exit_code == 0
    assert "Capturado" in result.output


def test_ask_exibe_resposta(mock_config):
    """ask exibe a resposta do LLM no terminal."""
    with patch("techlead.cli.commands._invoke_claude", return_value="Nenhum blocker no momento."):
        result = runner.invoke(app, ["ask", "o que está bloqueado no time?"])

    assert result.exit_code == 0
    assert "Nenhum blocker" in result.output


def test_draft_exibe_texto(mock_config):
    """draft exibe o texto gerado sem marcadores extras."""
    draft_text = "Olá CTO,\n\nSegue o status semanal do time..."
    with patch("techlead.cli.commands._invoke_claude", return_value=draft_text):
        result = runner.invoke(app, ["draft", "email de status semanal pro CTO"])

    assert result.exit_code == 0
    assert "status semanal" in result.output


def test_delegate_sem_agentes_avisa(mock_config):
    """delegate avisa quando não há agentes no registry."""
    with patch("techlead.core.registry.AGENTS_DIR") as mock_dir:
        mock_dir.exists.return_value = False
        result = runner.invoke(app, ["delegate", "verificar blockers do time"])

    assert result.exit_code == 0
    assert "Nenhum agente" in result.output


def test_sem_config_bloqueia_comandos(monkeypatch):
    """Comandos retornam erro se config não existir."""
    monkeypatch.setattr("techlead.cli.commands.load_config", lambda: {})

    for cmd in ["capture texto", "ask pergunta", "draft instrucao", "delegate tarefa"]:
        args = cmd.split()
        result = runner.invoke(app, args)
        assert "tlc init" in result.output
