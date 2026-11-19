# ADR 0008 — Gate de build scripts do pnpm nos Blueprints

Status: Aceito · Data: 2026-07-14 · Owner: team:engineering

> **Definição.** Blueprints que usam **pnpm** declaram
> `dangerouslyAllowAllBuilds: true` no `pnpm-workspace.yaml` do projeto gerado, para
> que o scaffolding não-interativo sobreviva ao gate de build scripts do pnpm 10+.

## Contexto

O pnpm 10+ (validado aqui na 11.1.2) **bloqueia por padrão** os lifecycle scripts
(`postinstall` etc.) das dependências como medida anti-supply-chain, e **aborta o
install com exit 1** (`ERR_PNPM_IGNORED_BUILDS`) até uma aprovação **interativa**
(`pnpm approve-builds`). Isso é incompatível com o bootstrap não-interativo do
`/maes-create`.

O gate dispara em três momentos, para deps com build script fora da allowlist padrão
do pnpm (ex.: `@swc/core`, `@parcel/watcher`, `@prisma/engines`, `prisma`,
`unrs-resolver`, `sharp`):

- install interno do scaffolder (`create-next-app`);
- `pnpm add` que introduz uma dep nova com build script (ex.: `@prisma/client`);
- o **dep-status check** que `next build` e `nest build` rodam antes de compilar —
  que reinvoca `pnpm install` e aborta.

Afeta os Blueprints pnpm (`nextjs-web`, `nestjs-api`). Não afeta `fastapi-api` (usa
`uv`) nem, na prática, o `react-spa` (o dep-set atual está na allowlist padrão do
pnpm e o `vite build` não reexecuta install).

## Decisão

- Os Blueprints pnpm **declaram `dangerouslyAllowAllBuilds: true`** no
  `pnpm-workspace.yaml` do projeto, **antes** dos `pnpm add` — via passo próprio do
  `bootstrap.yaml` (`nextjs-web` faz append no arquivo que o `create-next-app` gera;
  `nestjs-api` cria o arquivo, pois o `nest new` não o gera).
- Para o `create-next-app`, o scaffold usa `--skip-install`; o install roda no passo
  seguinte, já com o gate liberado.
- **Não enumeramos** as deps nativas em `onlyBuiltDependencies` — a lista sofre
  *drift* a cada bump de versão (e `onlyBuiltDependencies: []` não suprime o abort).

## Alternativas consideradas

- **Enumerar `onlyBuiltDependencies`** — rejeitada: frágil, sofre drift, e o modo
  vazio não impede o abort.
- **`pnpm approve-builds`** — rejeitada: interativo; incompatível com o agente.
- **`pnpm config set` global** — rejeitada: polui o ambiente do dev, não é
  reproduzível e não fica versionado no contrato do Blueprint.
- **Trocar de gerenciador (npm)** — rejeitada por ora: mudança maior; pnpm é o
  padrão da organização e o gate é contornável de forma escopada.

## Consequências

- O bootstrap não-interativo funciona ponta a ponta nos Blueprints pnpm; para o
  Prisma isso é **necessário** (o `postinstall` do `@prisma/client` roda
  `prisma generate`).
- **Trade-off explícito:** a flag desliga o guard anti-supply-chain **naquele
  projeto** — aceito porque um scaffold greenfield já executa código de ferramentas
  oficiais (`create-next-app`, `nest`, `shadcn`) e a stack é curada. É decisão
  consciente, registrada no `bootstrap.yaml` de cada Blueprint pnpm.
- Decisão escopada ao projeto gerado; não altera configuração global do dev.
