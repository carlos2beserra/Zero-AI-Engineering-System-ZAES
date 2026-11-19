---
layer: 5
ttl: 90d
owner: team:product
scope: []
confidence: explicit
source: ""
---

# Regras de Negócio

> Regras do domínio que não são inferíveis do código.
> Inclua invariantes, restrições de estado e o que o sistema explicitamente NÃO faz.
> Esta seção é crítica — sem ela, a IA vai adivinhar e errar.

## Invariantes do Domínio

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Saldo de conta nunca pode ser negativo — mesmo em transações parciais
- Pedido cancelado não pode ser reaberto — estado terminal
- Usuário com plano Free não pode ter mais de N projetos ativos simultaneamente
-->

## Transições de Estado

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- invoice: rascunho → pendente → pago/cancelado — sem atalhos entre estados
- Cancelamento de assinatura: sempre com 30 dias de aviso — nunca imediato por decisão do produto
- Aprovação de crédito: requer dois aprovadores para valores acima de threshold definido
-->

## O que o Sistema NÃO Faz

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Não processa estornos diretamente — todo estorno vai para fila manual de análise
- Não envia email em produção para domínios @example.com — filtro obrigatório
- Não permite deleção de usuários com transações ativas — soft-delete apenas
-->

## Regras de Elegibilidade

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Desconto de fidelidade: apenas clientes com > N meses de conta ativa
- Acesso à API pública: apenas planos Business e Enterprise — não disponível no Free
- Exportação de dados: máximo N registros por request — sem bypass para admins
-->

## Comportamentos Não-Óbvios

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Campo 'amount' armazena em centavos (integer) — nunca em float por problemas de precisão
- Timestamps de transações são em UTC — exibição em timezone do cliente é responsabilidade do frontend
- IDs são UUIDs v4 — não usar IDs sequenciais em nenhuma entidade do domínio financeiro
-->
