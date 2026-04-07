# PRD — techlead-cli

## Problem Statement

Tech leads operam num estado constante de sobrecarga cognitiva. Eles gerenciam múltiplos contextos simultâneos — sprints, OKRs, pessoas, stakeholders, decisões técnicas, visão estratégica — sem uma ferramenta que unifique essas dimensões num único ponto de controle. O resultado: a maior parte do tempo é consumida por tarefas operacionais e reativas, e o pensamento estratégico — que é onde o TL gera mais valor — raramente acontece. Context switching frequente drena energia mental e aumenta a chance de itens críticos caírem no esquecimento.

## Solution

`techlead-cli` é um sistema de CLI + agentes que atua como cockpit do tech lead. Ele consolida informações de múltiplas fontes (Jira, Confluence, GitHub, Google Calendar, Gmail, vault local) via MCPs, mantém um contexto persistente sobre time, projetos e OKRs, e usa LLM (Claude) para priorizar, sugerir e agir de forma proativa. O objetivo é reduzir o tempo gasto em trabalho operacional e liberar o TL para pensar estrategicamente.

O sistema roda como CLI com alias `tl`, dispara alertas via Slack, e opera de forma autônoma via cron job — sem exigir que o TL fique gerenciando a ferramenta.

## User Stories

1. Como tech lead, quero abrir o terminal de manhã e ver um briefing consolidado do meu dia, para não precisar abrir Jira, Calendar e Gmail separadamente.
2. Como tech lead, quero que o briefing tenha uma síntese gerada por LLM no topo com o que devo focar hoje, para tomar decisões de prioridade sem esforço mental.
3. Como tech lead, quero ver o estado atual dos OKRs do time no dashboard, para saber se estamos no caminho certo sem precisar consultar Confluence manualmente.
4. Como tech lead, quero ver quais pessoas do meu time estão bloqueadas hoje, para agir rapidamente e desbloquear o fluxo.
5. Como tech lead, quero ver minha agenda do dia com contexto de cada reunião (Jira + Confluence relevantes), para entrar em cada reunião preparado.
6. Como tech lead, quero ver PRs aguardando minha revisão no GitHub, para não ser o gargalo do time.
7. Como tech lead, quero receber alertas proativos no Slack quando algo crítico acontecer (blocker novo, OKR em risco, deadline se aproximando), para agir antes que vire problema.
8. Como tech lead, quero capturar uma decisão ou contexto importante com `tl capture "..."`, para não perder informação importante no meio do dia.
9. Como tech lead, quero fazer perguntas em linguagem natural com `tl ask "..."`, para consultar contexto sem lembrar de comandos específicos.
10. Como tech lead, quero que a CLI sugira itens estratégicos para eu me aprofundar, para não ficar 100% do tempo no operacional.
11. Como tech lead, quero configurar a CLI com `tl init` num wizard interativo, para não precisar editar arquivos de configuração manualmente.
12. Como tech lead, quero que novos agentes possam ser adicionados via arquivos YAML + `.md`, para expandir o sistema sem escrever código.
13. Como tech lead, quero que o contexto do sistema seja persistido entre sessões em arquivos `.md` locais, para não perder histórico de decisões e situações do time.
14. Como tech lead, quero que contextos antigos decaiam automaticamente por TTL configurável por tipo, para que o LLM receba apenas informação relevante.
15. Como tech lead, quero receber um draft de comunicação gerado por LLM (email, Slack, Confluence page) com `tl draft`, para reduzir tempo em escrita operacional.
16. Como tech lead, quero delegar uma tarefa para um sub-agente com `tl delegate`, para automatizar trabalho repetitivo.
17. Como tech lead, quero que o orchestrator rode via cron job e verifique o estado do meu contexto periodicamente, para receber alertas mesmo quando não estou com o terminal aberto.
18. Como tech lead, quero que o sistema use os MCPs nativos do Claude Code para acessar Jira, Confluence, GitHub, Calendar e Gmail, para não precisar gerenciar integrações customizadas.
19. Como tech lead, quero que meu vault local de `.md` seja incluído como fonte de contexto, para que notas pessoais sejam consideradas junto com dados externos.
20. Como tech lead, quero ver no dashboard o que está pendente da minha ação (aprovações, reviews, respostas), para não deixar o time esperando por mim.

## Implementation Decisions

### Arquitetura Geral

- Sistema construído sobre **Claude Code** como interface primária de agentes
- LLM utilizado: **Claude (Anthropic)** via Claude Code
- MCPs nativos substituem camadas de integração customizadas — sem código de connector
- O LLM decide qual MCP chamar baseado no contexto e nos MCPs disponíveis declarados no prompt do orchestrator

### Módulos

**`core/context-engine`**
- Memória persistente em arquivos `.md` com frontmatter YAML
- Uma entidade por arquivo: pessoa, projeto, OKR, decisão
- Cada entidade contém histórico cronológico de eventos dentro do arquivo
- TTL fixo por tipo de contexto, definido em `config.yml` (ex: blockers = 7 dias, decisões = 30 dias, OKRs = 90 dias)
- Script de decaimento executa via cron, remove eventos expirados

**`core/orchestrator`**
- Agente central responsável por coordenar sub-agentes e gerar o briefing
- Prompt define quais MCPs estão disponíveis e suas capacidades
- Detecta itens críticos e dispara alertas via Slack DM
- Roda via cron job (intervalo configurável, padrão: 15 minutos)

**`agents/`**
- Registry de agentes extensível
- Cada agente definido por dois arquivos: `agent-name.yml` (metadados, MCPs usados, trigger conditions) + `agent-name.md` (prompt/behavior)
- Nenhum código necessário para adicionar um novo agente
- Agentes iniciais: `jira-agent`, `okr-agent`, `people-agent`, `calendar-agent`

**`cli/`**
- Alias principal: `tl`
- Comandos iniciais:
  - `tl init` — wizard de configuração interativo
  - `tl brief` — dashboard matinal
  - `tl ask "<pergunta>"` — consulta em linguagem natural
  - `tl capture "<texto>"` — captura contexto/decisão
  - `tl draft "<instrução>"` — gera draft de comunicação
  - `tl delegate "<tarefa>"` — delega para sub-agente

### Dashboard (`tl brief`)

- Estrutura fixa com seções: OKRs, Blockers do Time, Agenda do Dia, PRs em Review, Pendências
- Parágrafo de síntese gerado por LLM no topo com foco do dia e sugestões estratégicas
- Dados puxados via MCPs na hora da execução

### Alertas

- Canal: **Slack DM** para o próprio TL
- Configurável por tipo/severidade em `config.yml`
- Disparados pelo orchestrator quando cron detecta item crítico

### Configuração

- Arquivo principal: `~/.techlead/config.yml`
- Setup via `tl init` — wizard interativo que valida credenciais na hora
- Credenciais de MCPs (Atlassian, GitHub, Google) configuradas via variáveis de ambiente referenciadas no config

### Stack

- Python 3.12.9
- `uv` como package manager
- `ruff` como linter/formatter
- Config em YAML

## Testing Decisions

- **O que faz um bom teste:** testa comportamento externo observável, não detalhes de implementação. Um teste deve quebrar quando o comportamento muda, não quando o código interno é refatorado.
- **Módulos com testes:**
  - `core/context-engine` — leitura, escrita, decaimento de contexto (TTL). Interface simples e isolada, ideal para unit tests.
  - `cli/commands` — parsing de comandos, validação de input do wizard `tl init`
  - `core/orchestrator` — lógica de detecção de itens críticos (com MCPs mockados)
- **Módulos sem testes no MVP:** `agents/` (behavior definido em prompts, difícil de testar deterministicamente)

## Out of Scope

- Métricas de time e OKRs (velocity, burndown) — fora do MVP
- Interface web ou mobile
- Multi-tenant / múltiplos usuários
- Integração com Linear, Notion, ou outras ferramentas além das definidas
- Autenticação própria (usa credenciais existentes dos MCPs)
- Histórico de auditoria de ações do agente

## Further Notes

- O sistema começa single-user (o próprio autor) e pode ser expandido para outros TLs se validado
- A ausência de métricas no MVP é intencional — o foco é reduzir carga cognitiva primeiro, medir depois
- O modelo mental do projeto: **"um chief of staff digital que roda no terminal"**
- Sucesso em 30 dias: menos tempo em tarefas operacionais, menos context switching, mais itens estratégicos chegando ao TL para pensar
- O sistema deve ser invisível quando funcionando bem — o TL não gerencia a ferramenta, a ferramenta gerencia o caos
