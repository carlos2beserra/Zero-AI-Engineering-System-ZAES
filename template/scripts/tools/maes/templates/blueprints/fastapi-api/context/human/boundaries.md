---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Boundaries e Placement — FastAPI API Corporativa

> Convenções de **onde o código deve nascer** (Intended Placement) e de
> **fronteiras entre camadas**. Padrão de referência definido pela organização —
> ajustável por decisão explícita, nunca pela IA. Regras com caminho viram guards
> de enforcement.

## Placement por camada

- Endpoints HTTP (routers) ficam em `app/api/v1/routes/` — nunca colocar regra de negócio no router.
- DTOs de request/response (Pydantic) ficam em `app/api/v1/schemas/` — nunca reaproveitar o model SQLModel como DTO de borda.
- Lógica de negócio fica em `app/services/<domain>/` — nunca acessar o banco (`session`) direto do router.
- Models de banco (SQLModel `table=True`) ficam em `app/db/models/` — nunca declarar model de tabela fora daqui.
- Configuração (settings) e taxonomia de erros ficam em `app/core/` — nunca duplicar leitura de env fora do settings.
- Adapters de sistemas externos ficam em `app/infrastructure/` — nunca chamar SDK externo (ex.: cliente de storage/fila) fora dessa camada.
- Permissões e vocabulário de domínio (RBAC) ficam em `app/domain/` — sem I/O.

## Regras de dependência (unidirecional)

- `app/db/models/**` nunca importa de `app/api/**` nem de `app/services/**` — os models não conhecem camadas acima.
- `app/infrastructure/**` nunca importa de `app/api/**` nem de `app/services/**` — a infraestrutura é folha.
- `app/workers/**` reusa `app/services/**` e nunca importa de `app/api/**` — workers não passam pela camada HTTP.
