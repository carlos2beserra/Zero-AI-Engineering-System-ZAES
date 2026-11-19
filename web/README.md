# MAES Web App

Next.js 15 application serving the MAES documentation site.

Part of the [MAES monorepo](../README.md).

## Stack

| | |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS + shadcn/ui |
| Docs engine | Fumadocs (MDX) |
| Testing | Vitest |

## Getting Started

**Prerequisites:** Node.js ≥ 20, npm ≥ 10

```bash
# From the web/ directory
npm install
npm run dev
```

## Commands

| Script | Description |
|--------|-------------|
| `npm run dev` | Starts dev server |
| `npm run build` | Production build |
| `npm start` | Starts production server |
| `npm test` | Runs Vitest test suite |
| `npm run test:watch` | Vitest in watch mode |
| `npm run test:coverage` | Vitest with V8 coverage report |
| `npm run lint` | ESLint via Next.js |
| `npm run type-check` | TypeScript check (no emit) |

## Project Structure

```
src/
  app/
    docs/          — Fumadocs routing (auto-generated from content/)
  shared/
    domain/maes/   — TypeScript domain types (ContextFile, etc.)

content/
  docs/            — MDX source for the docs site
```

## Further Reading

- Architecture + decisions: [`ai-context/core/architecture.md`](ai-context/core/architecture.md)
- Context navigation for AI tasks: [`ai-context/index.md`](ai-context/index.md)
- Docs site: [maes.maxxi.io/docs](https://maes.maxxi.io/docs)
