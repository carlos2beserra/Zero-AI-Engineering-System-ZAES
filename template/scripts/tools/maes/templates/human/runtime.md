---
layer: 6
ttl: 30d
owner: team:devops
scope: []
confidence: explicit
source: ""
last_verified: ""
test: ""
build: ""
lint: ""
run: ""
migrate: ""
test_pattern: ""
run_module_test: ""
---

# Runtime Context

> Comandos canônicos para executar testes, build, lint e migrações neste projeto.
> Mantenha curto e verificado — agentes copiam estes comandos literalmente.
> Atualize `last_verified` sempre que validar manualmente que ainda funcionam.
>
> Campos suportados no frontmatter (todos opcionais, vazios são omitidos):
>
> - `test` — Comando que roda toda a suite. Ex.: `pytest -q`
> - `build` — Build completo. Ex.: `pnpm build`
> - `lint` — Lint do projeto. Ex.: `ruff check .`
> - `run` — Inicia o servidor/app local. Ex.: `pnpm dev`
> - `migrate` — Aplica migrações. Ex.: `alembic upgrade head`
> - `test_pattern` — Como rodar testes que casam um padrão. Ex.: `pytest -k {pattern}`
> - `run_module_test` — Como rodar testes de um módulo específico. Ex.: `pytest tests/{module}`
> - `last_verified` — Data ISO (YYYY-MM-DD) da última verificação humana. **Obrigatório.**
>
> Se `last_verified` for mais antigo que 30 dias, `maes sync` emite um WARNING
> e os adapters marcam a seção como `⚠️ runtime context may be stale`.

## Notas

<!--
Use este espaço para documentar pré-requisitos do ambiente:
- Versões mínimas (Python 3.11, Node 20)
- Variáveis de ambiente obrigatórias
- Serviços externos requeridos (Postgres, Redis)
-->
