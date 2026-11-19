---
layer: 2
ttl: 180d
owner: team:security
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Autenticação e Autorização — Next.js Web App Corporativa

> Fronteira de auth definida pela organização. Regras de segurança — tier de
> maior prioridade.

## Sessão

- A sessão de autenticação deve ser compatível com SSR e segura — o token nunca fica em armazenamento só-cliente que quebre SSR ou exponha a sessão.

## Autorização

- A autorização exige dupla camada — permissões de tenant E capabilities de projeto — ambas devem passar para liberar uma ação de projeto.
- O guard de rota é declarativo (ex.: um `RouteGuard` que recebe a permissão exigida) — componentes nunca fazem fetch de autenticação nem decidem permissão por conta própria.
- A verificação de permissão é centralizada num motor de permissões compartilhado — nunca duplicar checagem de permissão espalhada em componentes.
