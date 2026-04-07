"""Testes do agent registry."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import techlead.core.registry as registry_mod


@pytest.fixture
def agents_dir(tmp_path, monkeypatch):
    """Cria um AGENTS_DIR temporário com agentes de teste."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    monkeypatch.setattr(registry_mod, "AGENTS_DIR", agents_dir)
    return agents_dir


def _create_agent(agents_dir: Path, name: str, description: str, with_prompt: bool = True) -> None:
    """Helper para criar agente de teste."""
    yml = agents_dir / f"{name}.yml"
    yml.write_text(yaml.dump({"name": name, "description": description}))
    if with_prompt:
        md = agents_dir / f"{name}.md"
        md.write_text(f"# {name}\nVocê é o agente {name}.")


def test_load_agents_vazio(agents_dir):
    """load_agents retorna lista vazia se não há agentes."""
    assert registry_mod.load_agents() == []


def test_load_agents_carrega_yml_e_md(agents_dir):
    """load_agents carrega YML e detecta arquivo .md correspondente."""
    _create_agent(agents_dir, "jira-agent", "Busca issues no Jira")

    agents = registry_mod.load_agents()
    assert len(agents) == 1
    assert agents[0]["name"] == "jira-agent"
    assert agents[0]["_prompt_file"] is not None


def test_load_agents_sem_prompt_file(agents_dir):
    """load_agents marca _prompt_file como None se .md não existe."""
    _create_agent(agents_dir, "okr-agent", "Analisa OKRs", with_prompt=False)

    agents = registry_mod.load_agents()
    assert agents[0]["_prompt_file"] is None


def test_select_agent_retorna_agente_valido(agents_dir):
    """select_agent retorna agente existente no registry."""
    _create_agent(agents_dir, "jira-agent", "Busca issues no Jira")
    _create_agent(agents_dir, "okr-agent", "Analisa OKRs")

    agents = registry_mod.load_agents()
    resposta = json.dumps({"agent_name": "jira-agent", "reason": "tarefa relacionada a Jira"})

    with patch("techlead.core.registry._invoke_claude", return_value=resposta):
        agent, reason = registry_mod.select_agent("verificar blockers no Jira", agents)

    assert agent is not None
    assert agent["name"] == "jira-agent"
    assert "Jira" in reason


def test_select_agent_fallback_agente_invalido(agents_dir):
    """select_agent retorna None com mensagem se LLM retorna agente inexistente."""
    _create_agent(agents_dir, "jira-agent", "Busca issues no Jira")
    agents = registry_mod.load_agents()

    resposta = json.dumps({"agent_name": "agente-fantasma", "reason": "não existe"})

    with patch("techlead.core.registry._invoke_claude", return_value=resposta):
        agent, reason = registry_mod.select_agent("qualquer tarefa", agents)

    assert agent is None
    assert "agente-fantasma" in reason
    assert "jira-agent" in reason


def test_select_agent_fallback_json_invalido(agents_dir):
    """select_agent retorna None se LLM não retorna JSON."""
    _create_agent(agents_dir, "jira-agent", "Busca issues no Jira")
    agents = registry_mod.load_agents()

    with patch("techlead.core.registry._invoke_claude", return_value="resposta sem json"):
        agent, reason = registry_mod.select_agent("qualquer tarefa", agents)

    assert agent is None


def test_run_agent_executa_com_prompt(agents_dir):
    """run_agent invoca claude com prompt do agente + contexto + tarefa."""
    _create_agent(agents_dir, "jira-agent", "Busca issues no Jira")
    agents = registry_mod.load_agents()
    agent = agents[0]

    with patch("techlead.core.registry._invoke_claude", return_value="resultado") as mock_claude:
        resultado = registry_mod.run_agent(agent, "verificar blockers", "contexto do TL")

    assert resultado == "resultado"
    prompt_usado = mock_claude.call_args[0][0]
    assert "verificar blockers" in prompt_usado
    assert "contexto do TL" in prompt_usado


def test_run_agent_sem_prompt_file_levanta_erro(agents_dir):
    """run_agent levanta RuntimeError se agente não tem arquivo .md."""
    _create_agent(agents_dir, "okr-agent", "Analisa OKRs", with_prompt=False)
    agents = registry_mod.load_agents()

    with pytest.raises(RuntimeError, match="sem arquivo de prompt"):
        registry_mod.run_agent(agents[0], "tarefa", "contexto")
