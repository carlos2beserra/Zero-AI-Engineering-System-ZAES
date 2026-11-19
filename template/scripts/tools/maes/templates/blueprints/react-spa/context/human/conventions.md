---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:react-spa"
---

# Convenções de Código — React SPA Corporativo

> Nomenclatura, organização de arquivos e padrões de teste homologados. Padrão de
> referência da organização — ajustável por decisão explícita, nunca pela IA.

## Nomenclatura de arquivos

- Componentes em PascalCase com extensão `.tsx` (`src/features/<feature>/PaymentForm.tsx`) — arquivo de componente nunca em `.ts`.
- Hooks nomeados `use*` em arquivos `use*.ts` — nunca declarar hook fora de um arquivo `use*`.
- Schemas Zod nomeados `*.schema.ts` em `src/features/<feature>/schemas/`.

## Componentes

- Um componente por arquivo; o nome do arquivo casa com o componente exportado.
- Componentes de feature nunca importam de `src/components/ui/**` estilos próprios — reutilizam o componente base como está.
- Componentes são renderizadores puros — a orquestração (dados, mutações, regras) vive em hooks de feature, nunca no componente.
- Estados de carregamento, vazio e erro de listas são centralizados no componente de lista/tabela compartilhado — features nunca reimplementam esses estados.

## Formulários

- O schema Zod fica colocado ao formulário (`*.schema.ts`) e é a fonte dos tipos — nunca validar à mão fora do schema.
- Separação container × presenter: o container detém a mutação e o erro de servidor; o formulário é puro — o formulário nunca chama a API diretamente.

## Testes

- Testes ficam ao lado do alvo como `*.test.tsx` usando Testing Library — nunca testar detalhes de implementação.
