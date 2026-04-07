"""Comando `tlc brief` — dashboard matinal."""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from techlead.core.config import load_config
from techlead.core.orchestrator import generate_brief

console = Console()


def brief_cmd() -> None:
    """Gera o briefing matinal consolidado."""
    config = load_config()
    if not config:
        console.print("[yellow]⚠[/yellow] Config não encontrada. Rode [bold]tlc init[/bold] primeiro.")
        return

    now = datetime.now()
    console.print(Rule(f"[bold]techlead brief — {now.strftime('%A, %d %b %Y')}[/bold]"))
    console.print()

    with console.status("[bold green]Coletando dados via MCPs...[/bold green]", spinner="dots"):
        try:
            briefing = generate_brief()
        except RuntimeError as e:
            console.print(f"[red]✗ Erro ao invocar Claude CLI:[/red]\n{e}")
            return
        except FileNotFoundError:
            console.print("[red]✗ Claude CLI não encontrado. Rode [bold]tlc init[/bold] para verificar.[/red]")
            return

    console.print(briefing)
    console.print()
    console.print(Rule(style="dim"))
