---
layer: 3
ttl: 30d
owner: team:platform
scope: []
confidence: explicit
source: ""
---

# Integrações Externas

> Integrações críticas, legadas ou não-óbvias.
> Inclua contratos, restrições e comportamentos que a IA não pode inferir do código.
> Atualizar sempre que uma integração mudar comportamento ou ter incidente.

## Integrações Ativas

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Gateway de pagamento: Stripe — usar apenas stripe-sdk (não client HTTP direto); webhooks devem ser validados com stripe-signature
- SMS: Twilio — rate limit de 1 msg/segundo por número; filas obrigatórias para disparos em massa
- Storage: S3-compatible (MinIO em dev, AWS S3 em prod) — sempre usar abstração em src/storage/
-->

## Integrações Legadas

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- ERP do cliente X: SOAP 1.1 via legacy/soap-client.ts — não modernizar sem autorização; integração tem contrato vigente
- Relatórios: integração FTP com parceiro Y — deposita CSV às 02:00 UTC; qualquer mudança de formato requer aviso de 30 dias
- Autenticação SSO: SAML 2.0 com provedor legado — não substituir por OAuth sem aprovação do cliente corporativo
-->

## Integrações "Aparentemente Mortas"

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- webhook-legacy.ts: parece morto mas ainda recebe eventos do parceiro Z — não remover sem confirmar com time de operações
- Coluna external_ref em orders: populada pela integração B2B — vazia para 90% dos pedidos mas crítica para clientes corporativos
-->

## Restrições de Rate Limit

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- API do Correios: 60 req/min — throttle implementado em services/shipping/correios.ts
- Geocoding (Google Maps API): quota de 1000 req/dia em dev — não usar em testes automatizados
- Parceiro de crédito: máximo 5 consultas/CPF/dia — verificar limite antes de qualquer chamada
-->

## Comportamentos Não-Óbvios

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Parceiro de logística retorna status em português (ENTREGUE, DEVOLVIDO) — não normalizar para inglês
- API de CEP tem latência de até 3s em horário de pico — timeout em 5s; sem retry automático (evita duplicação de cobrança)
-->
