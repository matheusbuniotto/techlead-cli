"""Registry de agentes — carrega e seleciona agentes do ~/.techlead/agents/."""

import json
import re
from pathlib import Path

import yaml

from techlead.core.config import AGENTS_DIR
from techlead.core.orchestrator import _invoke_claude


def load_agents() -> list[dict]:
    """Carrega todos os agentes disponíveis no registry."""
    agents = []
    if not AGENTS_DIR.exists():
        return agents

    for yml_file in sorted(AGENTS_DIR.glob("*.yml")):
        try:
            data = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
            md_file = yml_file.with_suffix(".md")
            data["_prompt_file"] = str(md_file) if md_file.exists() else None
            data["_slug"] = yml_file.stem
            agents.append(data)
        except yaml.YAMLError:
            continue

    return agents


def select_agent(task: str, agents: list[dict]) -> tuple[dict | None, str]:
    """
    Seleciona o agente mais adequado para a tarefa via LLM.

    Retorna (agente selecionado, razão) ou (None, mensagem de erro).
    """
    agents_summary = "\n".join(
        f"- {a.get('name', a['_slug'])}: {a.get('description', '')}"
        for a in agents
    )
    valid_names = {a.get("name", a["_slug"]) for a in agents}

    prompt = f"""Dado a tarefa abaixo, qual agente é o mais adequado?

Tarefa: "{task}"

Agentes disponíveis:
{agents_summary}

Responda APENAS com JSON:
{{"agent_name": "nome exato do agente", "reason": "motivo em uma frase"}}

O campo agent_name deve ser EXATAMENTE um dos nomes listados acima.
"""

    try:
        raw = _invoke_claude(prompt)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None, "LLM não retornou JSON válido"

        parsed = json.loads(match.group())
        chosen_name = parsed.get("agent_name", "")
        reason = parsed.get("reason", "")

        if chosen_name not in valid_names:
            return None, f"Agente '{chosen_name}' não existe no registry. Agentes válidos: {', '.join(sorted(valid_names))}"

        agent = next(a for a in agents if a.get("name", a["_slug"]) == chosen_name)
        return agent, reason

    except (json.JSONDecodeError, StopIteration) as e:
        return None, f"Erro ao selecionar agente: {e}"


def run_agent(agent: dict, task: str, context: str) -> str:
    """Executa um agente com a tarefa e contexto fornecidos."""
    prompt_file = agent.get("_prompt_file")
    if not prompt_file or not Path(prompt_file).exists():
        raise RuntimeError(f"Agente '{agent.get('name')}' sem arquivo de prompt (.md)")

    agent_prompt = Path(prompt_file).read_text(encoding="utf-8")

    full_prompt = f"""{agent_prompt}

## Contexto do tech lead
{context}

## Tarefa
{task}
"""
    return _invoke_claude(full_prompt)
