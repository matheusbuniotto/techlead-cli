"""Orchestrator — invoca o Claude CLI com contexto e MCPs para gerar o briefing."""

import json
import re
import subprocess
from datetime import datetime, timedelta

from techlead.core.context import recall

_BRIEF_PROMPT_TEMPLATE = """Você é o assistente de um tech lead. Sua missão agora é gerar o briefing matinal.

## Contexto local (memória persistente)

{context_block}

## O que fazer

Use os MCPs disponíveis para coletar informações atuais e monte um briefing no seguinte formato:

---

## 🎯 Foco do Dia
[Parágrafo curto gerado por você: o que o tech lead deve priorizar hoje e por quê. Base: contexto local + dados coletados. Inclua 1 sugestão estratégica se houver padrão relevante.]

## 📋 OKRs
[Liste os OKRs ativos e progresso atual. Busque no Confluence/Jira.]

## 🚧 Blockers do Time
[Liste pessoas bloqueadas e em quê. Busque no Jira — issues com status "Blocked" ou similar.]

## 📅 Agenda de Hoje
[Liste reuniões do dia com horário e contexto breve de cada uma. Busque no Google Calendar.]

## 🔍 PRs Aguardando Review
[Liste PRs abertos aguardando sua revisão. Busque no GitHub.]

## ✋ Pendências da Minha Ação
[Liste emails, mensagens ou itens que requerem uma ação sua. Busque no Gmail.]

{strategic_section}

---

Seja direto e objetivo. Sem enrolação. Se uma seção não tiver dados, escreva "Nada no momento."

## MCPs disponíveis
- Atlassian (Jira + Confluence): buscar issues, sprints, OKRs, pages
- GitHub: buscar PRs, reviews pendentes
- Google Calendar: buscar eventos do dia
- Gmail: buscar emails que requerem ação
"""


def _build_context_block() -> str:
    """Monta o bloco de contexto local para incluir no prompt."""
    entities = recall()
    if not entities:
        return "Nenhum contexto salvo ainda."

    lines = []
    for entity in entities:
        lines.append(f"### {entity['type'].capitalize()}: {entity['name']}")
        for event in entity["events"]:
            lines.append(f"- [{event['date'][:10]}] {event['text']}")
        lines.append("")

    return "\n".join(lines)


def _invoke_claude(prompt: str) -> str:
    """
    Invoca o Claude CLI com o prompt e retorna o output.

    Usa `claude -p` para modo não-interativo.
    """
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI falhou:\n{result.stderr}")
    return result.stdout.strip()


def _has_enough_history(min_days: int = 7) -> bool:
    """Verifica se há contexto histórico suficiente para visão estratégica."""
    entities = recall()
    if not entities:
        return False

    cutoff = datetime.now() - timedelta(days=min_days)
    for entity in entities:
        for event in entity["events"]:
            event_date = datetime.fromisoformat(event["date"])
            if event_date < cutoff:
                return True
    return False


def generate_strategic_vision(context_block: str) -> str | None:
    """
    Gera sugestões estratégicas baseadas no histórico acumulado.

    Retorna None se não houver contexto suficiente ou se todas as
    sugestões forem genéricas (filtro de especificidade).
    """
    if not _has_enough_history():
        return None

    # Gera sugestões
    prompt = f"""Você é o assistente estratégico de um tech lead. Com base no histórico abaixo, gere 2-3 sugestões estratégicas.

## Histórico acumulado
{context_block}

Cada sugestão deve:
- Citar explicitamente uma entidade, evento ou padrão concreto do histórico acima
- Ter horizonte de tempo ("nas próximas 2 semanas", "antes do fim do sprint")
- Ser específica para ESTE tech lead, não genérica

Formato de resposta — lista numerada, cada item em uma linha:
1. [sugestão com evidência específica e horizonte]
2. [sugestão com evidência específica e horizonte]
"""

    sugestoes_raw = _invoke_claude(prompt)

    # Filtro de especificidade: segundo prompt avalia cada sugestão
    filter_prompt = f"""Avalie as sugestões abaixo. Para cada uma, diga se é ESPECÍFICA (cita dado concreto do contexto) ou GENÉRICA (poderia ser dada a qualquer tech lead).

Sugestões:
{sugestoes_raw}

Responda com JSON:
{{"aprovadas": ["sugestão 1 completa", "sugestão 2 completa"], "reprovadas": ["sugestão genérica"]}}

Só aprove sugestões que citam pessoa, projeto, OKR ou evento específico.
"""

    filter_raw = _invoke_claude(filter_prompt)
    match = re.search(r"\{.*\}", filter_raw, re.DOTALL)
    if not match:
        return None

    try:
        resultado = json.loads(match.group())
        aprovadas = resultado.get("aprovadas", [])
    except json.JSONDecodeError:
        return None

    if not aprovadas:
        return None

    linhas = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(aprovadas))
    return linhas


def generate_brief() -> str:
    """Gera o briefing matinal completo via Claude CLI + MCPs."""
    context_block = _build_context_block()

    # Visão estratégica (opcional — só com histórico suficiente)
    strategic_section = ""
    vision = generate_strategic_vision(context_block)
    if vision:
        strategic_section = f"\n\n## 🧭 Visão Estratégica\n{vision}"

    prompt = _BRIEF_PROMPT_TEMPLATE.format(
        context_block=context_block,
        strategic_section=strategic_section,
    )
    return _invoke_claude(prompt)


def check_criticals() -> list[str]:
    """
    Verifica itens críticos e retorna lista de alertas.

    Usado pelo cron job para disparar notificações Slack.
    """
    prompt = """Você é o assistente de um tech lead. Verifique rapidamente se há itens críticos agora.

Use os MCPs disponíveis e retorne APENAS uma lista JSON de alertas no formato:
[{"severity": "high|medium", "message": "descrição curta do problema"}]

Considere crítico:
- Issues com status "Blocked" no Jira criados ou atualizados nas últimas 2 horas
- OKRs com progresso abaixo de 30% faltando menos de 2 semanas para o fim do período
- PRs sem review há mais de 24 horas
- Emails marcados como urgente não respondidos

Se não houver nada crítico, retorne: []

MCPs disponíveis: Atlassian (Jira + Confluence), GitHub, Gmail, Google Calendar.
"""
    raw = _invoke_claude(prompt)

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
        return [f"[{i.get('severity', '?').upper()}] {i.get('message', '')}" for i in items]
    except json.JSONDecodeError:
        return []
