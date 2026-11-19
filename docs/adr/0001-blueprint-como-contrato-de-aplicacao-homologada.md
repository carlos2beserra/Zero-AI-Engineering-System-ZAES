# ADR 0001 — Blueprint como contrato de governança de aplicação homologada

Status: Aceito · Data: 2026-07-11 · Owner: team:architecture

> **Definição.** Blueprint é uma **unidade de governança técnica de aplicação
> homologada** — **não é um template de código e não é um gerador de projetos.**
> O MAES permanece Engineering Orchestrator; nunca é scaffolder.

## Contexto

O MAES é um Engineering Orchestrator cujo motor interno é o Compiler
(Assertions → Representações: CLAUDE.md, Copilot, Cursor, MCP). Hoje ele só
cobre o fluxo brownfield (`maes init` → `/maes-analyze` → `maes sync`). A Fase 1
adiciona o primeiro fluxo greenfield: criar um projeto novo a partir de uma
opção homologada. Precisamos fixar o que é um "Blueprint" antes de escrever
código, para não escorregar de volta para um gerador de arquivos/scaffolder.

## Decisão

1. **Blueprint é uma unidade de governança técnica de aplicação homologada — não
   um template de código e não um gerador de projetos.** Compõe-se de:
   identidade/stack aprovada, contexto operacional, contexto organizacional e
   receita de bootstrap. Divisão de responsabilidade dentro do Blueprint:
   - `blueprint.yaml` = contrato determinístico (metadata: `id`, `name`, `type`,
     `version`, `summary`, `stack`, `seed_human`). Sem lógica de decisão,
     matching, intent ou execução.
   - `prompt.md` = contexto operacional para o Agent (objetivo, padrões,
     restrições, ferramentas obrigatórias). **Não executa comandos, sem lógica
     de decisão.**
   - `bootstrap/bootstrap.yaml` = **única fonte de execução** (Official First).
     Toda chamada de ferramenta parte daqui.
   - `context/human/` = contexto organizacional inicial (princípios, decisões,
     compliance, regras corporativas). Não é documentação do projeto gerado.
2. **Blueprint não é scaffolder.** O MAES nunca reimplementa Vite/Nest CLI/etc.
   A criação usa exclusivamente ferramentas oficiais do ecossistema (Official
   First); o Blueprint apenas declara a receita.
3. **O usuário escolhe; o Agent executa; a organização governa o catálogo.**
   A decisão arquitetural pertence à organização (define o catálogo) e ao
   usuário (seleciona explicitamente por nome/id/número). O `/maes-create`
   **nunca decide, sugere ou infere stack** — sem match por intenção, keywords
   ou recomendação automática (Blueprint Selection Principle).
4. **Divisão de responsabilidade CLI × Agent:** o CLI (`maes blueprint
   list/show/prompt/seed/validate`) é determinístico e nunca cria projeto nem
   roda scaffold; o Agent `/maes-create` orquestra a execução via ferramentas
   oficiais e só acessa o catálogo através do CLI (nunca lê
   `templates/blueprints/` diretamente).
5. **Contexto organizacional é semeado** do Blueprint (`context/human/*`) para
   `.maes/context/human/`, tornando o projeto AI-ready desde o nascimento.

## Consequências

- O motor (Compiler), o MCP e o fluxo brownfield permanecem intactos — a Fase 1
  só consome o `maes sync` existente.
- O catálogo vive empacotado no CLI (`templates/blueprints/`), versionado pela
  engenharia; a evolução/validação via `analyze` fica para depois (não inverter
  a ordem).
- Nenhuma abstração futura (Registry, Marketplace, Capability, Asset, Planner,
  Executor, OCI, Update) é introduzida.
