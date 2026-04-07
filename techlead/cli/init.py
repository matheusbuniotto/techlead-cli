"""Comando `tlc init` — wizard de configuração interativo."""

import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from techlead.core.config import ensure_dirs, load_config, save_config

console = Console()


def _check_claude_cli() -> bool:
    """Verifica se o claude CLI está disponível no PATH."""
    return shutil.which("claude") is not None


def _check_gh_cli() -> bool:
    """Verifica se o gh CLI está disponível e autenticado."""
    if not shutil.which("gh"):
        return False
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    return result.returncode == 0


def _setup_cron(interval_minutes: int) -> bool:
    """Adiciona ou atualiza o cron job do orchestrator."""
    import os
    import tempfile

    tlc_path = shutil.which("tlc") or "tlc"
    cron_cmd = f"*/{interval_minutes} * * * * {tlc_path} _cron"
    marker = "# techlead-cli"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    lines = [l for l in existing.splitlines() if marker not in l]
    lines.append(f"{cron_cmd} {marker}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cron", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        tmp = f.name

    result = subprocess.run(["crontab", tmp], capture_output=True)
    os.unlink(tmp)
    return result.returncode == 0


def init_cmd(
    force: Annotated[bool, typer.Option("--force", help="Reconfigurar mesmo se já existe config")] = False,
) -> None:
    """Configura o techlead-cli interativamente."""
    console.print(Panel.fit("🦝 techlead-cli — setup", style="bold green"))

    # Verifica dependências
    if not _check_claude_cli():
        console.print("[red]✗[/red] Claude CLI não encontrado no PATH.")
        console.print("  Instale em: https://claude.ai/code")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Claude CLI encontrado.")

    if _check_gh_cli():
        console.print("[green]✓[/green] GitHub CLI (gh) encontrado e autenticado.")
    else:
        console.print("[yellow]⚠[/yellow] GitHub CLI não encontrado ou não autenticado.")
        console.print("  Instale com: brew install gh && gh auth login")

    config = load_config()

    if config and not force:
        console.print("\n[yellow]Config existente encontrada.[/yellow] Use --force para reconfigurar.")
        _show_config_summary(config)
        return

    console.print("\n[bold]Vamos configurar suas integrações.[/bold]\n")

    # Atlassian via MCP
    console.print("[bold cyan]Atlassian (Jira + Confluence)[/bold cyan]")
    console.print("  Usado via MCP do Claude Code — configure o MCP Atlassian antes de continuar.")
    console.print("  Docs: https://github.com/sooperset/mcp-atlassian")
    atlassian_url = Prompt.ask(
        "  URL do seu Jira (ex: https://minhaempresa.atlassian.net)",
        default=config.get("atlassian", {}).get("url", ""),
    )
    atlassian_configured = Confirm.ask("  MCP Atlassian já está configurado no Claude Code?", default=False)

    # GitHub via gh CLI
    console.print("\n[bold cyan]GitHub[/bold cyan]")
    console.print("  Usado via [bold]gh[/bold] CLI — sem token manual necessário.")
    if _check_gh_cli():
        console.print("  [green]✓[/green] gh já está autenticado.")
        github_configured = True
    else:
        console.print("  [yellow]⚠[/yellow] Configure com: gh auth login")
        github_configured = Confirm.ask("  gh já está autenticado?", default=False)

    # Google via MCP
    console.print("\n[bold cyan]Google (Calendar + Gmail)[/bold cyan]")
    console.print("  Usado via MCP do Claude Code.")
    console.print("  Docs: https://github.com/modelcontextprotocol/servers")
    google_configured = Confirm.ask("  MCP do Google já está configurado no Claude Code?", default=False)

    # Slack via Webhook
    console.print("\n[bold cyan]Slack — Alertas via Webhook[/bold cyan]")
    console.print("  Para receber alertas no Slack, crie um Workflow:")
    console.print("  1. Abra o Slack → Automações → Criar workflow")
    console.print("  2. Trigger: [bold]Webhook[/bold]")
    console.print("  3. Ação: enviar mensagem para você mesmo")
    console.print("  4. Copie a URL do webhook gerada")
    slack_webhook = Prompt.ask(
        "  Webhook URL (deixe vazio para pular)",
        default=config.get("slack", {}).get("webhook_url", ""),
    )

    # Vault local
    console.print("\n[bold cyan]Vault local (.md)[/bold cyan]")
    vault_path = Prompt.ask(
        "  Caminho do vault (deixe vazio para pular)",
        default=config.get("vault", {}).get("path", ""),
    )

    # TTLs de contexto
    console.print("\n[bold cyan]Decaimento de contexto (TTL em dias)[/bold cyan]")
    ttl_blocker = int(Prompt.ask("  Blockers", default=str(config.get("ttl", {}).get("blocker", 7))))
    ttl_decision = int(Prompt.ask("  Decisões", default=str(config.get("ttl", {}).get("decision", 30))))
    ttl_okr = int(Prompt.ask("  OKRs", default=str(config.get("ttl", {}).get("okr", 90))))

    # Cron
    console.print("\n[bold cyan]Orchestrator (cron)[/bold cyan]")
    cron_interval = int(Prompt.ask(
        "  Intervalo de verificação (minutos)",
        default=str(config.get("cron", {}).get("interval_minutes", 15)),
    ))

    # Monta config
    new_config = {
        "atlassian": {
            "url": atlassian_url,
            "configured": atlassian_configured,
        },
        "github": {
            "configured": github_configured,
        },
        "google": {
            "configured": google_configured,
        },
        "slack": {
            "webhook_url": slack_webhook,
        },
        "vault": {
            "path": vault_path,
        },
        "ttl": {
            "blocker": ttl_blocker,
            "decision": ttl_decision,
            "okr": ttl_okr,
        },
        "cron": {
            "interval_minutes": cron_interval,
        },
    }

    # Salva
    save_config(new_config)
    ensure_dirs()
    console.print("\n[green]✓[/green] Config salva em ~/.techlead/config.yml")
    _install_default_agents()

    # Configura cron
    console.print("Configurando cron job...", end=" ")
    if _setup_cron(cron_interval):
        console.print(f"[green]✓[/green] a cada {cron_interval} minutos")
    else:
        console.print("[yellow]⚠ falhou — configure manualmente com `crontab -e`[/yellow]")

    console.print(Panel.fit("[bold green]Setup completo! Rode `tlc brief` para começar.[/bold green]"))


def _install_default_agents() -> None:
    """Copia os agentes padrão para ~/.techlead/agents/ se não existirem."""
    from techlead.core.config import AGENTS_DIR

    defaults_dir = Path(__file__).parent.parent / "agents" / "defaults"
    if not defaults_dir.exists():
        return

    installed = 0
    for src in defaults_dir.iterdir():
        dst = AGENTS_DIR / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            installed += 1

    if installed:
        console.print(f"[green]✓[/green] {installed} agente(s) padrão instalado(s) em ~/.techlead/agents/")


def _show_config_summary(config: dict) -> None:
    """Exibe resumo da config atual."""
    console.print("\n[bold]Config atual:[/bold]")
    atlassian = config.get("atlassian", {})
    if atlassian.get("url"):
        console.print(f"  Atlassian: {atlassian['url']} (MCP: {'✓' if atlassian.get('configured') else '✗'})")
    github = config.get("github", {})
    console.print(f"  GitHub: gh CLI ({'✓ autenticado' if github.get('configured') else '✗ não configurado'})")
    slack = config.get("slack", {})
    if slack.get("webhook_url"):
        console.print(f"  Slack: webhook configurado ✓")
    vault = config.get("vault", {})
    if vault.get("path"):
        console.print(f"  Vault: {vault['path']}")
    cron = config.get("cron", {})
    console.print(f"  Cron: a cada {cron.get('interval_minutes', 15)} minutos")
