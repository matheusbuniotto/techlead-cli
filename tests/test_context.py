"""Testes do context engine."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import techlead.core.context as ctx


@pytest.fixture(autouse=True)
def isolate_context(tmp_path, monkeypatch):
    """Redireciona CONTEXT_DIR para tmp_path em todos os testes."""
    context_dir = tmp_path / "context"
    for subdir in ["person", "project", "okr", "decision"]:
        (context_dir / subdir).mkdir(parents=True)
    monkeypatch.setattr(ctx, "CONTEXT_DIR", context_dir)


def test_save_cria_entidade():
    """save cria arquivo .md com frontmatter e evento."""
    ctx.save("person", "João Silva", "Está bloqueado na PROJ-42", event_type="blocker")

    path = ctx.CONTEXT_DIR / "person" / "joão-silva.md"
    assert path.exists()
    content = path.read_text()
    assert "João Silva" in content
    assert "Está bloqueado na PROJ-42" in content
    assert "expires_at" in content


def test_save_acumula_eventos():
    """save acumula múltiplos eventos na mesma entidade."""
    ctx.save("project", "Projeto Alpha", "Kickoff realizado")
    ctx.save("project", "Projeto Alpha", "Sprint 1 iniciada")

    results = ctx.recall("project", "Projeto Alpha")
    assert len(results) == 1
    assert len(results[0]["events"]) == 2


def test_recall_retorna_apenas_eventos_validos(monkeypatch):
    """recall filtra eventos expirados."""
    ctx.save("decision", "Usar SQLite", "Decidido usar SQLite para métricas")

    # Expira manualmente o evento substituindo expires_at por data passada
    import re
    path = ctx.CONTEXT_DIR / "decision" / "usar-sqlite.md"
    content = path.read_text()
    past_date = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    content = re.sub(r"expires_at: '?[\d\-T:]+'?", f"expires_at: '{past_date}'", content)
    path.write_text(content)

    results = ctx.recall("decision", "Usar SQLite")
    assert results[0]["events"] == []


def test_recall_sem_filtro_retorna_todos():
    """recall sem argumentos retorna entidades de todos os tipos."""
    ctx.save("person", "Ana", "Tech lead do time de plataforma")
    ctx.save("okr", "OKR Q2", "Meta: 90% de uptime")

    results = ctx.recall()
    tipos = {r["type"] for r in results}
    assert "person" in tipos
    assert "okr" in tipos


def test_decay_remove_eventos_expirados():
    """decay remove eventos com expires_at no passado."""
    ctx.save("project", "Projeto Beta", "Reunião de alinhamento")

    path = ctx.CONTEXT_DIR / "project" / "projeto-beta.md"
    content = path.read_text()
    future_date = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
    past_date = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    content = content.replace(future_date, past_date)
    path.write_text(content)

    removed = ctx.decay()
    assert removed == 1

    results = ctx.recall("project", "Projeto Beta")
    assert results[0]["events"] == []


def test_decay_preserva_eventos_validos():
    """decay não remove eventos ainda válidos."""
    ctx.save("person", "Maria", "Promovida a sênior")
    ctx.save("person", "Maria", "Novo projeto atribuído")

    removed = ctx.decay()
    assert removed == 0

    results = ctx.recall("person", "Maria")
    assert len(results[0]["events"]) == 2
