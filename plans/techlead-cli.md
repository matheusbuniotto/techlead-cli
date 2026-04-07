# Plan: techlead-cli

> Source PRD: PRD.md

## Architectural Decisions

Decisões duráveis que se aplicam a todas as fases:

- **CLI entrypoint:** alias `tl` via Typer, comandos como `tl <verbo>`
- **LLM runtime:** Claude Code CLI (`claude` subprocess) — usa subscription existente, MCPs já configurados nativamente
- **MCP access:** nativo via Claude Code — nenhuma camada de integração customizada
- **Contexto persistente:** arquivos `.md` com frontmatter YAML em `~/.techlead/context/`
- **Config:** `~/.techlead/config.yml` — credenciais, TTLs, Slack user ID, intervalo do cron
- **Alertas:** Slack DM via `slack-sdk`
- **Scheduler:** crontab nativo — configurado automaticamente pelo `tl init`
- **Agent registry:** `~/.techlead/agents/` — cada agente tem `<name>.yml` + `<name>.md`
- **Stack:** Python 3.12.9, `uv`, `ruff`, YAML

---

## Phase 1: Foundation + Setup

**User stories:** 11, 18

### What to build

Scaffolding completo do projeto e wizard de configuração interativo. O usuário roda `tl init`, responde perguntas sobre suas credenciais (Atlassian, GitHub, Google, Slack), e a CLI valida cada integração via MCP antes de salvar. Ao final, `~/.techlead/config.yml` existe e está pronto para uso.

O `tl --help` deve listar todos os comandos disponíveis com descrições.

### Acceptance criteria

- [ ] `uv init` + `uv python pin 3.12.9` + dependências iniciais (Typer, PyYAML, slack-sdk) configuradas
- [ ] `tl --help` exibe todos os comandos com descrições
- [ ] `tl init` roda wizard interativo perguntando credenciais de cada integração
- [ ] `tl init` valida que o `claude` CLI está disponível no PATH
- [ ] `tl init` escreve `~/.techlead/config.yml` com todas as configurações
- [ ] `tl init` cria estrutura de diretórios: `~/.techlead/context/`, `~/.techlead/agents/`
- [ ] `tl init` configura cron job no crontab do sistema (intervalo padrão: 15min)
- [ ] Rodar `tl init` novamente atualiza config sem sobrescrever dados existentes

---

## Phase 2: Context Engine

**User stories:** 13, 14

### What to build

Motor de memória persistente. O sistema consegue salvar e recuperar contexto sobre entidades (pessoas, projetos, OKRs, decisões) em arquivos `.md` com frontmatter YAML. Um script de decaimento remove eventos expirados baseado em TTL configurável por tipo de entidade.

### Acceptance criteria

- [ ] Entidades são salvas em `~/.techlead/context/<type>/<name>.md` com frontmatter (name, type, created_at, updated_at)
- [ ] Cada entidade tem seção de histórico com eventos cronológicos e campo `expires_at` por evento
- [ ] TTLs por tipo definidos em `config.yml` (ex: `blocker: 7d`, `decision: 30d`, `okr: 90d`)
- [ ] Script de decaimento remove eventos com `expires_at` no passado
- [ ] Script de decaimento é executado pelo cron job junto com o orchestrator
- [ ] Interface interna: `context.save(entity, event)`, `context.recall(query)` retorna entidades relevantes
- [ ] Testes unitários cobrem: salvar evento, recuperar entidade, decaimento de evento expirado

---

## Phase 3: `tl brief` — Dashboard Matinal

**User stories:** 1, 2, 3, 4, 5, 6, 20

### What to build

Comando principal da CLI. O usuário roda `tl brief` e recebe no terminal um dashboard consolidado com seções estruturadas de dados reais + parágrafo de síntese gerado por LLM no topo. O orchestrator invoca o `claude` CLI com um prompt que declara os MCPs disponíveis e instrui a montar o briefing.

### Acceptance criteria

- [ ] `tl brief` executa o orchestrator via subprocess do `claude` CLI
- [ ] Dashboard exibe seções: OKRs, Blockers do Time, Agenda do Dia, PRs em Review, Pendências da minha ação
- [ ] Cada seção é populada com dados reais via MCPs (Atlassian, GitHub, Google Calendar, Gmail)
- [ ] Parágrafo de síntese LLM aparece no topo com foco do dia e sugestão estratégica
- [ ] Contexto salvo no context-engine é incluído no prompt do orchestrator
- [ ] Output formatado e legível no terminal (sem JSON bruto)
- [ ] Tempo de execução aceitável (< 60 segundos)

---

## Phase 4: Comandos Manuais

**User stories:** 8, 9, 15, 16

### What to build

Quatro comandos de interação direta que o TL usa durante o dia. Cada um invoca o `claude` CLI com prompt especializado e contexto relevante do context-engine.

- `tl capture "<texto>"` — salva uma decisão ou contexto no context-engine
- `tl ask "<pergunta>"` — consulta em linguagem natural, Claude responde usando MCPs + contexto
- `tl draft "<instrução>"` — gera draft de comunicação (email, Slack, Confluence)
- `tl delegate "<tarefa>"` — passa tarefa para um sub-agente do registry

### Acceptance criteria

- [ ] `tl capture "..."` salva o texto como evento no context-engine com tipo inferido por LLM
- [ ] `tl ask "..."` retorna resposta em linguagem natural usando dados dos MCPs e contexto local
- [ ] `tl draft "..."` retorna draft formatado pronto para copiar/colar
- [ ] `tl delegate "..."` identifica o agente mais adequado no registry e executa
- [ ] Todos os comandos incluem contexto relevante do context-engine no prompt
- [ ] Respostas são exibidas de forma limpa no terminal

---

## Phase 5: Alertas Proativos

**User stories:** 7, 17

### What to build

O orchestrator roda via cron job a cada 15 minutos (configurável). Ele verifica o estado atual via MCPs, compara com o contexto salvo, detecta itens críticos (novo blocker, OKR em risco, deadline próximo) e envia Slack DM quando necessário. Evita spam com controle de alertas já enviados.

### Acceptance criteria

- [ ] Cron job invoca o orchestrator no intervalo configurado
- [ ] Orchestrator detecta: novos blockers, OKRs em risco, deadlines em 24h, PRs parados há mais de 1 dia
- [ ] Alerta enviado via Slack DM para o user ID configurado em `config.yml`
- [ ] Cada alerta inclui contexto suficiente para o TL agir sem abrir outras ferramentas
- [ ] Sistema de deduplicação evita enviar o mesmo alerta duas vezes no mesmo dia
- [ ] Severidade do alerta configurável (quais tipos disparam notificação)
- [ ] `tl init` configura o cron entry corretamente em Linux e macOS

---

## Phase 6: Agent Registry

**User stories:** 12

### What to build

Sistema extensível de agentes. O TL (ou qualquer usuário) pode adicionar um novo agente criando dois arquivos em `~/.techlead/agents/`: um YAML de metadados e um `.md` de prompt/behavior. O `tl delegate` carrega o registry dinamicamente e escolhe o agente certo. Agentes iniciais incluídos: `jira-agent`, `okr-agent`, `people-agent`, `calendar-agent`.

### Acceptance criteria

- [ ] `~/.techlead/agents/<name>.yml` define: name, description, mcps, trigger_conditions
- [ ] `~/.techlead/agents/<name>.md` define o prompt/behavior do agente
- [ ] `tl delegate` lista agentes disponíveis e seleciona o mais adequado via LLM
- [ ] Adicionar um novo agente não requer nenhuma alteração de código
- [ ] Agentes iniciais funcionando: `jira-agent`, `okr-agent`, `people-agent`, `calendar-agent`
- [ ] `tl agents` lista todos os agentes disponíveis com descrição

---

## Phase 7: Visão Estratégica

**User stories:** 10

### What to build

Com contexto acumulado de semanas de uso, o orchestrator passa a incluir no `tl brief` sugestões estratégicas geradas por LLM — temas que o TL deveria se aprofundar, padrões detectados no time, riscos emergentes. Usa o histórico do context-engine como base.

### Acceptance criteria

- [ ] `tl brief` inclui seção "Visão Estratégica" com 2-3 sugestões geradas por LLM
- [ ] Sugestões são baseadas no histórico do context-engine (mínimo 7 dias de dados)
- [ ] Sugestões são distintas das operacionais — foco em tendências, não tarefas
- [ ] TL pode dar feedback com `tl capture "sobre sugestão X: ..."` para refinar futuras sugestões
- [ ] Seção é omitida se não houver contexto histórico suficiente
