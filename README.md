# techlead — Claude Code Plugin

Cockpit do tech lead como plugin do Claude Code. Briefing matinal, captura de contexto, e consultas em linguagem natural — tudo usando MCPs nativos.

## Instalação

```bash
claude plugin add /path/to/techlead-cli-skill-refactor
```

Ou simplesmente abra o Claude Code neste diretório e os comandos estarão disponíveis.

## Comandos

### `/tl-brief`

Gera o briefing matinal consolidado:

- **Foco do Dia** — síntese inteligente do que priorizar
- **OKRs** — progresso dos objetivos (via Confluence)
- **Blockers** — quem está travado e em quê (via Jira)
- **Agenda** — reuniões do dia (via Google Calendar)
- **PRs** — reviews pendentes (via GitHub)
- **Pendências** — emails que requerem ação (via Gmail)

```
> /tl-brief
```

### `/tl-capture`

Captura decisões, contexto ou observações na memória persistente:

```
> /tl-capture "João está bloqueado esperando deploy de staging"
> /tl-capture "Decidimos usar PostgreSQL" --type decision --entity database-choice
```

O contexto é salvo em `~/.techlead/context/` como arquivos `.md` com frontmatter YAML.

### `/tl-ask`

Consulta em linguagem natural usando contexto local + MCPs:

```
> /tl-ask "Quem está bloqueado hoje?"
> /tl-ask "O que tenho na agenda amanhã?"
> /tl-ask "O que decidimos sobre o banco de dados?"
```

## Memória Persistente

O contexto é salvo em `~/.techlead/context/` organizado por tipo:

```
~/.techlead/
├── config.yml          # Configurações (TTLs, etc)
└── context/
    ├── person/         # Pessoas do time
    ├── project/        # Projetos
    ├── okr/            # OKRs
    └── decision/       # Decisões técnicas
```

Cada entidade é um arquivo `.md`:

```markdown
---
name: João
type: person
created_at: 2024-01-15T10:30:00
updated_at: 2024-01-20T14:00:00
---

## Histórico

<!-- event: {date: '2024-01-20T14:00:00', event_type: person, expires_at: '2024-02-19T14:00:00'} -->
Bloqueado esperando deploy de staging

<!-- event: {date: '2024-01-15T10:30:00', event_type: person, expires_at: '2024-02-14T10:30:00'} -->
Começou a trabalhar no projeto X
```

### TTL (Time-to-Live)

Eventos expiram automaticamente por tipo:

| Tipo | TTL padrão |
|------|------------|
| person | 30 dias |
| project | 30 dias |
| okr | 90 dias |
| decision | 30 dias |
| blocker | 7 dias |

Customize em `~/.techlead/config.yml`:

```yaml
ttl:
  person: 60
  blocker: 14
```

## MCPs Necessários

O plugin usa os seguintes MCPs (conecte via Claude Code):

- **Google Calendar** — agenda do dia
- **Gmail** — emails pendentes
- **Atlassian (Jira + Confluence)** — sprints, blockers, OKRs
- **GitHub** — PRs aguardando review

## Estrutura do Plugin

```
techlead-cli-skill-refactor/
├── .claude-plugin/
│   └── plugin.json       # Manifest do plugin
├── commands/
│   ├── tl-brief.md       # /tl-brief
│   ├── tl-capture.md     # /tl-capture
│   └── tl-ask.md         # /tl-ask
└── scripts/
    └── context.py        # Engine de contexto local
```

## Desenvolvimento

O script de contexto pode ser testado diretamente:

```bash
# Inicializar estrutura
uv run scripts/context.py init

# Capturar evento
uv run scripts/context.py capture --type person --entity joao --text "Bloqueado no deploy"

# Listar contexto
uv run scripts/context.py recall

# Remover eventos expirados
uv run scripts/context.py decay
```
