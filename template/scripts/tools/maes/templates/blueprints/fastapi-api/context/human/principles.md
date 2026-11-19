---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Princípios de Engenharia — FastAPI API Corporativa

> Padrões de engenharia definidos pela organização para APIs FastAPI. Padrão de
> referência aderente por padrão em projetos criados a partir deste Blueprint —
> ajustável por decisão explícita, nunca pela IA.

## Padrões do Time

- Routers são finos — validam entrada, chamam um service e formatam a resposta; regra de negócio nunca vive no router.
- Toda regra de negócio e orquestração de transação vive na camada de services — nunca no router nem no model.
- Configuração vem de um único objeto de settings (pydantic-settings) — nunca ler `os.getenv` espalhado pelo código.
- Workers tratam a mensagem da fila como um ponteiro e recarregam tudo do banco — o banco é a fonte de verdade, nunca o payload da mensagem.
- Official First — a estrutura do projeto nasce das ferramentas oficiais (`uv`, `alembic`); o time nunca reimplementa scaffolding.
