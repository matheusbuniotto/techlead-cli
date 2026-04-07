"""Testes do módulo de deduplicação de alertas."""

import pytest

import techlead.core.alerts as alerts_mod


@pytest.fixture(autouse=True)
def isolate_alerts(tmp_path, monkeypatch):
    """Redireciona TECHLEAD_DIR e _ALERTS_FILE para tmp_path."""
    monkeypatch.setattr(alerts_mod, "_ALERTS_FILE", tmp_path / "alerts-sent.json")
    monkeypatch.setattr("techlead.core.alerts.TECHLEAD_DIR", tmp_path)


def test_filter_new_retorna_todos_se_nenhum_enviado():
    """filter_new retorna todos os alertas se nenhum foi enviado hoje."""
    alertas = ["[HIGH] João bloqueado", "[MEDIUM] OKR em risco"]
    assert alerts_mod.filter_new(alertas) == alertas


def test_filter_new_remove_ja_enviados():
    """filter_new remove alertas já enviados hoje."""
    alertas = ["[HIGH] João bloqueado", "[MEDIUM] OKR em risco"]
    alerts_mod.mark_sent(alertas[:1])

    novos = alerts_mod.filter_new(alertas)
    assert len(novos) == 1
    assert novos[0] == "[MEDIUM] OKR em risco"


def test_mark_sent_persiste_entre_chamadas():
    """mark_sent persiste o estado — filter_new o lê corretamente."""
    alerta = ["[HIGH] Deploy falhou"]
    alerts_mod.mark_sent(alerta)

    # Simula nova execução do cron
    assert alerts_mod.filter_new(alerta) == []


def test_alertas_diferentes_nao_deduplicam():
    """Alertas com conteúdo diferente não são bloqueados por deduplicação."""
    alerts_mod.mark_sent(["[HIGH] PR parado há 24h"])
    novos = alerts_mod.filter_new(["[HIGH] Novo blocker detectado"])
    assert len(novos) == 1


def test_limpeza_de_entradas_antigas(monkeypatch):
    """mark_sent remove entradas com mais de 7 dias."""
    from datetime import date, timedelta

    data_antiga = (date.today() - timedelta(days=8)).isoformat()

    # Injeta entrada antiga diretamente
    import json
    alerts_file = alerts_mod._ALERTS_FILE
    alerts_file.parent.mkdir(parents=True, exist_ok=True)
    alerts_file.write_text(json.dumps({
        "abc123": {"date": data_antiga, "alert": "alerta antigo"}
    }))

    # mark_sent deve limpar a entrada antiga
    alerts_mod.mark_sent(["[LOW] Novo alerta"])

    dados = json.loads(alerts_file.read_text())
    assert not any(v["date"] == data_antiga for v in dados.values())
