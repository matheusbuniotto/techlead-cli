"""Testes da visão estratégica (Phase 7)."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, call

import pytest

import techlead.core.context as ctx
import techlead.core.orchestrator as orch


@pytest.fixture(autouse=True)
def isolate_context(tmp_path, monkeypatch):
    """Isola o context engine em tmp_path."""
    context_dir = tmp_path / "context"
    for sub in ["person", "project", "okr", "decision"]:
        (context_dir / sub).mkdir(parents=True)
    monkeypatch.setattr(ctx, "CONTEXT_DIR", context_dir)


def _save_old_event(name: str, text: str, days_ago: int = 10) -> None:
    """Salva evento e retrodata para simular histórico antigo."""
    ctx.save("project", name, text)
    path = ctx.CONTEXT_DIR / "project" / f"{name.lower().replace(' ', '-')}.md"
    content = path.read_text()
    old_date = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
    # Substitui a data do evento (primeira ocorrência de date:)
    import re
    content = re.sub(
        r"date: '?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'?",
        f"date: '{old_date}'",
        content,
        count=1,
    )
    path.write_text(content)


def test_sem_historico_nao_gera_visao():
    """generate_strategic_vision retorna None se não há contexto salvo."""
    result = orch.generate_strategic_vision("sem contexto")
    assert result is None


def test_historico_recente_nao_gera_visao():
    """generate_strategic_vision retorna None se todo contexto tem menos de 7 dias."""
    ctx.save("project", "Alpha", "Sprint iniciada hoje")

    result = orch.generate_strategic_vision("contexto recente")
    assert result is None


def test_historico_suficiente_gera_visao():
    """generate_strategic_vision retorna sugestões com histórico de 7+ dias."""
    _save_old_event("Projeto Beta", "OKR Q2 em risco — apenas 20% concluído")

    sugestoes_raw = "1. Com base no OKR Q2 em risco do Projeto Beta, priorize revisão nas próximas 2 semanas."
    filter_resp = json.dumps({
        "aprovadas": ["Com base no OKR Q2 em risco do Projeto Beta, priorize revisão nas próximas 2 semanas."],
        "reprovadas": [],
    })

    with patch("techlead.core.orchestrator._invoke_claude", side_effect=[sugestoes_raw, filter_resp]):
        result = orch.generate_strategic_vision("contexto com OKR em risco")

    assert result is not None
    assert "Projeto Beta" in result or "OKR Q2" in result


def test_filtro_remove_sugestoes_genericas():
    """generate_strategic_vision retorna None se filtro reprovar todas as sugestões."""
    _save_old_event("Projeto Gamma", "Reunião de kickoff realizada")

    sugestoes_raw = "1. Considere alinhar melhor o time com os OKRs."
    filter_resp = json.dumps({
        "aprovadas": [],
        "reprovadas": ["Considere alinhar melhor o time com os OKRs."],
    })

    with patch("techlead.core.orchestrator._invoke_claude", side_effect=[sugestoes_raw, filter_resp]):
        result = orch.generate_strategic_vision("contexto qualquer")

    assert result is None


def test_filtro_json_invalido_retorna_none():
    """generate_strategic_vision retorna None se filtro não retornar JSON válido."""
    _save_old_event("Projeto Delta", "Deploy realizado com sucesso")

    with patch("techlead.core.orchestrator._invoke_claude", side_effect=["sugestão", "resposta inválida"]):
        result = orch.generate_strategic_vision("contexto qualquer")

    assert result is None


def test_visao_omitida_no_brief_sem_historico():
    """generate_brief não inclui seção estratégica sem histórico suficiente."""
    briefing_resp = "## 🎯 Foco do Dia\nFoco nos blockers."

    with patch("techlead.core.orchestrator._invoke_claude", return_value=briefing_resp) as mock:
        result = orch.generate_brief()

    # Sem histórico, generate_strategic_vision retorna None
    # O brief é gerado com strategic_section vazio
    prompt_usado = mock.call_args[0][0]
    assert "🧭 Visão Estratégica" not in prompt_usado
