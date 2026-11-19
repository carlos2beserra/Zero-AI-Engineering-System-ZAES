---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Workers e Infraestrutura — FastAPI API Corporativa

> Convenção **condicional**: aplica-se quando a API tem processamento assíncrono
> (workers/fila) ou integra sistemas externos (armazenamento, fila). Padrão de
> referência definido pela organização.

## Adapters de infraestrutura

- Todo acesso a sistema externo (fila, armazenamento, cripto) passa por um adapter isolado em `app/infrastructure/` — services nunca chamam o SDK externo diretamente.
- Os adapters expõem funções simples sobre o SDK; o equivalente de desenvolvimento (ex.: endpoint local) é injetado por settings — nunca hardcodar credencial ou endpoint no adapter.

## Workers

- Workers ficam em `app/workers/` e rodam como processo próprio (`python -m app.workers.<x>`) — nunca acoplar worker ao processo HTTP.
- O worker reusa a camada de services e cria sua própria `Session` — um worker nunca importa de `app/api/**`.
- A mensagem da fila carrega apenas um identificador; o worker recarrega o estado do banco (fonte de verdade) — nunca confiar em dados vindos no corpo da mensagem.
- A mensagem só é removida da fila após o trabalho atingir estado terminal, com verificação de idempotência para entrega duplicada — nunca deletar a mensagem antes de concluir.
