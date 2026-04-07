---
name: tl-capture
description: Captura uma decisão, contexto ou evento na memória persistente do tech lead
args:
  - name: text
    description: O texto a capturar (decisão, contexto, observação)
    required: true
  - name: type
    description: "Tipo da entidade: person, project, okr, decision"
    required: false
  - name: entity
    description: Nome da entidade relacionada (pessoa, projeto, etc)
    required: false
---

# Capturar Contexto

Você é o assistente de um tech lead. O usuário quer capturar uma informação na memória persistente.

## Argumentos Recebidos

- **text**: {text}
- **type** (opcional): {type}
- **entity** (opcional): {entity}

## Passo 1: Inferir Metadados (se não fornecidos)

Se `type` ou `entity` não foram fornecidos, analise o texto e infira:

- **person**: menções a pessoas do time, feedbacks, 1:1s
- **project**: atualizações de projeto, decisões técnicas
- **okr**: progresso de objetivos, métricas, key results
- **decision**: decisões tomadas, trade-offs, escolhas arquiteturais

Exemplos:
- "João está bloqueado no deploy" → type=person, entity=joao
- "Decidimos usar PostgreSQL ao invés de MongoDB" → type=decision, entity=database-choice
- "OKR de performance: atingimos 80% da meta" → type=okr, entity=performance-okr

## Passo 2: Salvar na Memória

Execute o script de contexto:

```bash
uv run --quiet ${CLAUDE_PLUGIN_ROOT}/scripts/context.py capture --type "<type>" --entity "<entity>" --text "<text>"
```

## Passo 3: Confirmar

Após salvar, confirme ao usuário:

> ✓ Capturado em `<type>/<entity>.md`: "<resumo do texto>"

Se houver entradas anteriores para essa entidade, mencione quantas existem:

> (3 eventos anteriores para esta entidade)
