---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Convenções de Código — Next.js Web App Corporativa

> Nomenclatura e imports definidos pela organização. Padrão de referência
> ajustável por decisão explícita.

## Nomenclatura de arquivos

- Módulos não-componentes usam sufixo por papel, em kebab/dot-segment: `<feature>.api.ts`, `<feature>.hooks.ts`, `<feature>.types.ts`, `<feature>.schema.ts`, `*.mapper.ts` — o papel nunca fica implícito no nome.
- Componentes React usam PascalCase no nome do arquivo (`ProjectForm.tsx`); primitivos shadcn em `src/shared/components/ui/` seguem o padrão da CLI (kebab-case).
- Hooks são nomeados `useXxx` em arquivos `use*` — nunca declarar hook fora de um arquivo `use*`.

## Imports

- Imports internos usam sempre o alias de raiz do projeto (`@`) — nunca cadeias relativas profundas entre camadas.
- Subdiretórios compartilhados expõem um barrel `index.ts` — o consumo passa pelo barrel, não por caminhos internos.

## Query keys

- Cada feature expõe uma fábrica `<feature>QueryKeys` com tuplas `as const` — chaves de query nunca são strings ad hoc.
