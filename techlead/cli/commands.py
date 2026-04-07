"""Comandos manuais: capture, ask, draft, delegate."""

from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from techlead.core.config import load_config
from techlead.core.context import recall, save
from techlead.core.orchestrator import _invoke_claude

console = Console()


def _require_config() -> dict:
    """Garante que a config existe antes de executar um comando."""
    config = load_config()
    if not config:
        console.print("[yellow]⚠[/yellow] Config não encontrada. Rode [bold]tlc init[/bold] primeiro.")
        raise typer.Exit(1)
    return config


def _context_summary() -> str:
    """Retorna resumo do contexto local para incluir nos prompts."""
    entities = recall()
    if not entities:
        return "Nenhum contexto salvo."

    lines = []
    for entity in entities:
        lines.append(f"[{entity['type']}] {entity['name']}")
        for event in entity["events"][:3]:  # máximo 3 eventos por entidade
            lines.append(f"  - {event['text']}")
    return "\n".join(lines)


def capture_cmd(
    texto: Annotated[str, typer.Argument(help="Decisão ou contexto a capturar")],
) -> None:
    """Captura uma decisão ou contexto importante na memória."""
    _require_config()

    # Usa LLM para classificar o texto e extrair entidade
    prompt = f"""Classifique o texto abaixo e extraia a entidade principal.

Texto: "{texto}"

Responda APENAS com JSON no formato:
{{"entity_type": "person|project|okr|decision", "entity_name": "nome da entidade", "event_type": "blocker|decision|update|okr|general"}}

Exemplos:
- "João está bloqueado na PROJ-42" -> {{"entity_type": "person", "entity_name": "João", "event_type": "blocker"}}
- "Decidimos usar SQLite para métricas" -> {{"entity_type": "decision", "entity_name": "SQLite para métricas", "event_type": "decision"}}
- "OKR Q2: meta de 90% uptime" -> {{"entity_type": "okr", "entity_name": "OKR Q2", "event_type": "okr"}}
"""

    import json
    import re

    try:
        raw = _invoke_claude(prompt)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            entity_type = parsed.get("entity_type", "decision")
            entity_name = parsed.get("entity_name", "geral")
            event_type = parsed.get("event_type", "general")
        else:
            entity_type, entity_name, event_type = "decision", "geral", "general"
    except Exception:
        entity_type, entity_name, event_type = "decision", "geral", "general"

    save(entity_type, entity_name, texto, event_type=event_type)  # type: ignore[arg-type]
    console.print(f"[green]✓[/green] Capturado como [bold]{entity_type}/{entity_name}[/bold]")


def ask_cmd(
    pergunta: Annotated[str, typer.Argument(help="Pergunta em linguagem natural")],
) -> None:
    """Consulta em linguagem natural usando MCPs e contexto local."""
    _require_config()

    context = _context_summary()
    prompt = f"""Você é o assistente de um tech lead. Responda a pergunta abaixo usando os MCPs disponíveis e o contexto local.

## Contexto local
{context}

## Pergunta
{pergunta}

## MCPs disponíveis
- Atlassian (Jira + Confluence): issues, sprints, OKRs, pages
- GitHub: PRs, commits, reviews
- Google Calendar: eventos e reuniões
- Gmail: emails

Seja direto e objetivo. Use dados reais dos MCPs quando relevante.
"""

    console.print()
    with console.status("[bold green]Consultando...[/bold green]", spinner="dots"):
        try:
            resposta = _invoke_claude(prompt)
        except (RuntimeError, FileNotFoundError) as e:
            console.print(f"[red]✗[/red] {e}")
            return

    console.print(Markdown(resposta))
    console.print()


def draft_cmd(
    instrucao: Annotated[str, typer.Argument(help="O que redigir (ex: 'email de status semanal pro CTO')")],
) -> None:
    """Gera um draft de comunicação pronto para usar."""
    _require_config()

    context = _context_summary()
    prompt = f"""Você é o assistente de um tech lead. Redija o seguinte:

"{instrucao}"

## Contexto disponível
{context}

## MCPs disponíveis para buscar dados adicionais
- Atlassian (Jira + Confluence)
- GitHub
- Google Calendar
- Gmail

Entregue APENAS o texto final do draft, formatado e pronto para copiar/colar.
Sem explicações adicionais. Sem marcadores de "aqui está o draft:".
"""

    console.print()
    with console.status("[bold green]Redigindo...[/bold green]", spinner="dots"):
        try:
            draft = _invoke_claude(prompt)
        except (RuntimeError, FileNotFoundError) as e:
            console.print(f"[red]✗[/red] {e}")
            return

    console.print(Rule("[bold]Draft[/bold]"))
    console.print()
    console.print(draft)
    console.print()
    console.print(Rule(style="dim"))


def delegate_cmd(
    tarefa: Annotated[str, typer.Argument(help="Tarefa a delegar para um sub-agente")],
) -> None:
    """Delega uma tarefa para o sub-agente mais adequado do registry."""
    from techlead.core.registry import load_agents, run_agent, select_agent

    _require_config()

    agents = load_agents()
    if not agents:
        console.print("[yellow]⚠[/yellow] Nenhum agente encontrado em ~/.techlead/agents/")
        console.print("  Rode [bold]tlc init[/bold] para instalar os agentes padrão.")
        return

    context = _context_summary()

    with console.status("[bold green]Selecionando agente...[/bold green]", spinner="dots"):
        agent, reason = select_agent(tarefa, agents)

    if agent is None:
        console.print(f"[red]✗ Não foi possível selecionar agente:[/red] {reason}")
        return

    agent_name = agent.get("name", agent["_slug"])
    console.print(f"[bold]Agente:[/bold] {agent_name} — {reason}")
    console.print()

    with console.status(f"[bold green]{agent_name} executando...[/bold green]", spinner="dots"):
        try:
            resultado = run_agent(agent, tarefa, context)
        except (RuntimeError, FileNotFoundError) as e:
            console.print(f"[red]✗[/red] {e}")
            return

    console.print(Markdown(resultado))


def agents_cmd() -> None:
    """Lista todos os agentes disponíveis no registry."""
    from techlead.core.registry import load_agents

    agents = load_agents()
    if not agents:
        console.print("[yellow]Nenhum agente encontrado em ~/.techlead/agents/[/yellow]")
        console.print("Rode [bold]tlc init[/bold] para instalar os agentes padrão.")
        return

    console.print(f"\n[bold]{len(agents)} agente(s) disponível(is):[/bold]\n")
    for agent in agents:
        name = agent.get("name", agent["_slug"])
        desc = agent.get("description", "sem descrição")
        has_prompt = "✓" if agent.get("_prompt_file") else "✗"
        console.print(f"  [green]{has_prompt}[/green] [bold]{name}[/bold] — {desc}")
    console.print()
