# Instruções GitHub Copilot — MAES

Você está trabalhando em um projeto governado pelo MAES (Maxxi AI Engineering System).
Aplique estes padrões em todas as sugestões.

---

## Padrões de Código

Regras completas: `.maes/context/human/principles.md`
Arquitetura e stack: `.maes/context/human/decisions.md`
Regras de domínio: `.maes/context/human/business-rules.md`
Contratos externos: `.maes/context/human/integrations.md`

---

## Em Toda Sugestão

- Valide input em todas as bordas do sistema (handlers HTTP, consumers, webhooks)
- Inclua tratamento de erro para todas as integrações externas
- Separe responsabilidades: controller ≠ service ≠ repository
- Use transactions em operações multi-tabela
- Adicione rate limiting e autenticação em endpoints públicos
- Isole integrações externas em camada adapter/gateway

---

## Contexto por Tipo de Task

Para injetar contexto no Chat, use `#file:`:

| Task              | Arquivos a injetar                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| Novo endpoint     | `#file:.maes/context/human/principles.md` `#file:.maes/context/human/decisions.md`                     |
| Lógica de domínio | `#file:.maes/context/human/business-rules.md` `#file:.maes/context/human/compliance.md`                |
| Bug fix           | `#file:.maes/context/human/decisions.md` `#file:.maes/context/human/principles.md`                     |
| Refatoração       | `#file:.maes/context/human/principles.md` `#file:.maes/context/human/decisions.md`                     |

Contexto compilado: `.maes/synthesis/` — gerado por `maes sync`
