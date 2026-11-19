---
layer: 1
ttl: 365d
owner: team:security
scope: []
confidence: explicit
source: ""
---

# Compliance e Regulação

> Regras regulatórias e de compliance que impactam o desenvolvimento.
> Preencher com as regras específicas do seu projeto.
> Qualquer item aqui tem prioridade máxima — nunca sobrescrito por padrões de código.

## Proteção de Dados

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Dados de PII nunca devem aparecer em logs de aplicação ou respostas de erro
- Endpoints com dados pessoais devem gerar registro em audit_events
- Retenção de dados: PII deve ser removida após N dias de inatividade da conta
-->

## Segurança

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Credenciais nunca armazenadas em plaintext — sempre via secret manager ou variáveis de ambiente cifradas
- TLS obrigatório em todas as conexões externas — sem exceção para ambientes de staging
- Tokens de API devem ter TTL máximo de N horas — sem tokens de longa duração em produção
-->

## Auditoria

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Toda operação destrutiva (delete, update em massa) deve gerar audit log com user_id, timestamp e payload anterior
- Audit logs são imutáveis — nenhum processo pode deletar ou editar registros de audit
-->

## Regulação Específica

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- LGPD: usuários têm direito de solicitar exclusão de todos os seus dados — endpoint obrigatório
- PCI-DSS: dados de cartão nunca persistidos — apenas token do gateway de pagamento
-->
