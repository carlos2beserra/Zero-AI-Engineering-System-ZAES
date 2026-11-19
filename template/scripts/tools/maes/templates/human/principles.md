---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: ""
---

# Princípios de Engenharia

> Princípios e padrões específicos deste time que vão além das regras gerais.
> Inclua APENAS o que diverge ou complementa as engineering-rules padrão do MAES.

## Padrões do Time

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Error handling: sempre usar classes de erro tipadas em src/errors/ — sem throw de string ou Error genérico
- Sem business logic em controllers/handlers — tudo passa pelos domain services
- Transactions explícitas para qualquer operação que afete mais de uma tabela
- DI sempre via construtor — nunca injeção via property ou método
-->

## Testes

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Testes de integração sempre contra banco real — sem mock de repositórios
- Coverage mínimo de N% em domain services — não em controllers
- Testes E2E para os fluxos críticos do produto
-->

## Performance

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Queries com > N ms de latência em P99 precisam de análise antes do merge
- Sem N+1 queries — usar eager loading ou DataLoader explicitamente
- Índices obrigatórios em foreign keys e colunas usadas em WHERE de endpoints de listagem
-->

## Convenções de Nomenclatura

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Entidades de domínio: PascalCase singular (User, Invoice, Payment)
- Eventos de domínio: PascalCase com sufixo Event (PaymentCreatedEvent)
- Repositórios: sufixo Repository (UserRepository)
-->

## Anti-Patterns Proibidos

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Sem God classes — classe com > N linhas precisa de justificativa
- Sem imports circulares — CI falha se detectar
- Sem variáveis globais mutáveis — use DI container ou módulo singleton explícito
-->

## Ferramentas e Processo

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- SonarLint deve passar sem issues antes de qualquer merge — extensão VS Code obrigatória para o time
- Coverage mínimo de 80% em domain services — verificado em CI, PR bloqueado se abaixo
- Pre-commit hooks obrigatórios: linting, type-check e testes unitários — sem bypass com --no-verify
- Commits seguem Conventional Commits: feat(scope): descrição, fix(scope): descrição, chore(scope): descrição
- Branch naming: feat/, fix/, chore/, hotfix/ — PRs sem prefixo reconhecido são rejeitados pelo CI
- Todos os PRs requerem aprovação de 2 revisores — definido no CODEOWNERS, sem exceção
- CI/CD via GitHub Actions — não CircleCI nem Jenkins; qualquer pipeline novo vai em .github/workflows/
-->
