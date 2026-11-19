# ADR 0002 — Distribuição oficial do MAES via AWS CodeArtifact (pacote Python)

Status: Aceito · Data: 2026-07-11 · Owner: team:architecture

> **Definição.** O MAES é distribuído **exclusivamente como pacote Python** (wheel)
> publicado em um repositório privado formato PyPI no **AWS CodeArtifact**. Não há pacote
> npm, launcher Node, instalador intermediário nem ambiente virtual gerenciado pelo MAES.
> O MAES permanece um **Engineering Orchestrator** — uma CLI Python tradicional.

## Contexto

Hoje o MAES só pode ser instalado clonando o repositório e rodando `bash install.sh`
(que faz `pipx install template/scripts/tools`). Não existe artefato publicado e o CI
apenas roda `pytest`. Isso impede que um desenvolvedor da organização instale a
ferramenta sem acesso ao repositório e sem conhecer sua estrutura interna.

A Fase 1.5 transforma o MAES em uma **CLI Python corporativa** instalável sem clone,
usando o AWS CodeArtifact como registry privado. Esta fase é **exclusivamente sobre
empacotamento e distribuição**: o motor (Compiler), os agents, os templates, os
blueprints, o `maes doctor` e o sistema de upgrade permanecem intactos.

Terminologia (para evitar leitura equivocada de "publicamos no PyPI"):

- **PyPI** = protocolo/formato de distribuição de pacotes Python.
- **AWS CodeArtifact** = o registry privado (repositório formato PyPI).
- **`pypi.org`** = apenas **upstream público** do CodeArtifact, usado para resolver
  dependências transitivas. **Não há publicação no `pypi.org`.**

## Decisão

1. **Canal único e artefato oficial.** A instalação oficial é
   `pip install maes[all]` a partir do CodeArtifact. O artefato oficial é o wheel
   `maes-X.Y.Z.whl` (a sdist `maes-X.Y.Z.tar.gz` é gerada para ferramentas internas). Não
   se documenta clone, `bash install.sh`, `pip install` local ou `pipx` como canal
   oficial — essas vias permanecem apenas para desenvolvimento/manutenção.

2. **Nome oficial congelado.** O nome do pacote no CodeArtifact, o comando da CLI e o
   pacote Python de import são todos `maes`:
   - package (distribuição) = `maes`
   - comando CLI = `maes`
   - import Python = `import maes`

   Não usar `maxxi-maes`, `maes-cli` ou `maes-engineering`.

3. **Fonte única de versão.** A versão vive em `maes/__init__.py` (`__version__`); o
   `pyproject.toml` a lê dinamicamente e a git tag `vX.Y.Z` deve coincidir. O wheel é
   **apenas o artefato gerado — nunca a fonte de versão**. O release aborta (guard) se
   `maes.__version__ != pyproject != git tag`.

4. **SemVer.** MAJOR = mudança incompatível na CLI/API; MINOR = novo
   blueprint/template/comando; PATCH = bugfix/documentação. Toda publicação exige o
   `CHANGELOG.md` atualizado.

5. **Ambiente Python é do consumidor.** O MAES **não** cria nem gerencia venv. O
   consumidor usa venv, pipx, uv ou ferramenta corporativa. O core roda em Python 3.9+;
   o canal oficial `maes[all]` requer **Python 3.10+** (o extra inclui `mcp`).

6. **Conteúdo do wheel.** O pacote embarca Compiler, agents, templates e **blueprints**
   (via `package-data` / `MANIFEST.in`). A versão do catálogo de blueprints é, portanto,
   a versão do CLI que os embarca.

7. **Release por tag, com OIDC.** O pipeline dispara em tag `v*`, roda em Python 3.11
   fixo (build reproduzível) e separa `build → validate → publish`; a publicação só
   ocorre após o wheel ser instalado e validado por smoke test. A autenticação AWS usa
   **OIDC** (GitHub Actions assume uma IAM Role) — **sem access key fixa**.

8. **Pré-requisito de infraestrutura.** O repositório PyPI do CodeArtifact precisa de
   **upstream para o `pypi.org`** para resolver as dependências transitivas (`pyyaml`,
   `anthropic`, `openai`, `mcp`, `pydantic-core`, etc.). Sem isso, `pip install maes[all]`
   falha mesmo com o wheel publicado.

9. **Governança de versões.** Versões publicadas são **imutáveis** — nunca sobrescrever
   uma versão existente; remoção de versão é processo manual documentado no
   `docs/RELEASING.md`. O **rollback** é o fluxo pip padrão (`pip install maes==X.Y.Z`);
   não existe mecanismo próprio de rollback/update do MAES.

## Consequências

- O motor (Compiler), o MCP, os agents, os templates, os blueprints, o `maes doctor` e o
  sistema de upgrade permanecem **inalterados** — esta fase só empacota e distribui.
- Nenhuma abstração de distribuição alternativa é introduzida: sem npm, Node, launcher,
  `package.json`, `install.js`, `bin/maes.js`, `postinstall`, venv gerenciado, Registry
  próprio, Marketplace, servidor MAES, catálogo externo ou update system.
- `pipx install maes` (a partir do CodeArtifact) e `bash install.sh` (a partir do clone)
  permanecem compatíveis para desenvolvimento/manutenção, mas **não** fazem parte da
  experiência oficial de consumo.
- O consumidor precisa de acesso ao CodeArtifact (via `aws sso login` +
  `aws codeartifact login --tool pip`) e de um Python compatível — a responsabilidade do
  ambiente Python é da equipe consumidora.
