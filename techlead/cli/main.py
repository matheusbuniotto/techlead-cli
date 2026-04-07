"""Entrypoint principal da CLI techlead."""

import typer

from techlead.cli.brief import brief_cmd
from techlead.cli.commands import agents_cmd, ask_cmd, capture_cmd, delegate_cmd, draft_cmd
from techlead.cli.cron import cron_cmd
from techlead.cli.init import init_cmd

app = typer.Typer(
    name="tlc",
    help="Cockpit do tech lead — menos caos, mais foco.",
    no_args_is_help=True,
)

app.command("init", help="Configura o techlead-cli interativamente.")(init_cmd)
app.command("brief", help="Gera o briefing matinal consolidado.")(brief_cmd)
app.command("capture", help="Captura uma decisão ou contexto na memória.")(capture_cmd)
app.command("ask", help="Consulta em linguagem natural usando MCPs e contexto.")(ask_cmd)
app.command("draft", help="Gera um draft de comunicação pronto para usar.")(draft_cmd)
app.command("delegate", help="Delega uma tarefa para um sub-agente.")(delegate_cmd)
app.command("agents", help="Lista os agentes disponíveis no registry.")(agents_cmd)
app.command("_cron", help="Executado pelo cron — verifica críticos e dispara alertas.", hidden=True)(cron_cmd)


def main() -> None:
    """Executa a CLI."""
    app()
