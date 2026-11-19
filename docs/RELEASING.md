# Releasing MAES

O MAES é publicado como pacote Python em um repositório privado formato PyPI no
**AWS CodeArtifact**. Este runbook cobre o processo de release, a configuração de
infraestrutura, permissões IAM/OIDC, governança de versões, rollback e troubleshooting.

> Terminologia: **PyPI** = formato/protocolo de pacote Python · **CodeArtifact** = o
> registry privado · **`pypi.org`** = apenas upstream público para resolver dependências.
> **Não há publicação no `pypi.org`.**

---

## Fluxos suportados

Existem dois fluxos independentes. A **publicação só acontece durante um release** — o
desenvolvimento nunca publica nada.

### Desenvolvimento (contribuidores)

- Clone do repositório.
- Editable install: `pip install -e ".[dev,all]"` em `template/scripts/tools`.
- Execução local da CLI (`maes …`) — alterações no código ficam imediatamente disponíveis.
- Testes: `pytest -q` (inclui os testes de empacotamento).
- **Não** gera wheel, **não** publica no CodeArtifact e **não** cria tags para testar.

### Distribuição (release)

1. **Build** — `python -m build` gera wheel + sdist (Python 3.11 fixo), com guard de versão.
2. **Validação** — instala o wheel em um virtualenv limpo e roda o smoke test.
3. **Publicação** — `twine upload` para o AWS CodeArtifact, autenticado via OIDC.
4. **Instalação corporativa** — consumidores rodam `pip install maes[all]` (ver README).

A publicação (passo 3) só ocorre no workflow de release, disparado por tag `v*`, e **somente
após** o build e a validação passarem.

---

## Fonte de verdade da versão

```
maes/__init__.py  (__version__)  →  pyproject.toml (dynamic)  →  git tag vX.Y.Z
```

- A versão vive em [`template/scripts/tools/maes/__init__.py`](../template/scripts/tools/maes/__init__.py).
- `pyproject.toml` lê essa versão dinamicamente (`[tool.setuptools.dynamic]`).
- A **git tag `vX.Y.Z` deve coincidir** — o job `build` do release aborta se divergirem.
- O wheel é **apenas o artefato gerado**, nunca a fonte.

## Versionamento (SemVer)

| Incremento | Quando |
|---|---|
| **MAJOR** | mudança incompatível na CLI/API |
| **MINOR** | novo blueprint / template / comando |
| **PATCH** | bugfix / documentação |

**Toda publicação exige o [`CHANGELOG.md`](../CHANGELOG.md) atualizado.**

---

## Fazer um release

1. Atualize `maes/__init__.py` (`__version__ = "X.Y.Z"`).
2. Atualize o `CHANGELOG.md` com a entrada da versão.
3. Commit + PR + merge na `main` (o `build-check` do CI valida o empacotamento).
4. Crie e envie a tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. O workflow [`release.yml`](../.github/workflows/release.yml) dispara e executa três
   jobs **encadeados** — a publicação só ocorre se os anteriores passarem:

   ```
   build     → guard de versão → python -m build → twine check → sha256sum
   validate  → instala o wheel em venv limpo → smoke (--version, blueprint list, init --help)
   publish   → OIDC → aws codeartifact login --tool twine → twine upload
   ```

O ambiente de build é **Python 3.11 fixo** (reproduzível); o artefato validado é
exatamente o publicado.

---

## Configuração da infraestrutura

### Upstream do PyPI (obrigatório)

O repositório PyPI do CodeArtifact **precisa de upstream para o `pypi.org`**, senão as
dependências transitivas (`pyyaml`, `anthropic`, `openai`, `mcp`, `pydantic-core`, …)
não resolvem e `pip install maes[all]` falha mesmo com o wheel publicado.

### GitHub Variables (não Secrets)

Configure em *Settings → Secrets and variables → Actions → Variables*:

| Variable | Descrição |
|---|---|
| `AWS_ROLE_TO_ASSUME` | ARN da IAM Role assumida via OIDC |
| `AWS_REGION` | ex.: `us-east-1` |
| `CODEARTIFACT_DOMAIN` | nome do domínio CodeArtifact |
| `CODEARTIFACT_OWNER` | domain owner (AWS account id) |
| `CODEARTIFACT_REPOSITORY` | nome do repositório (formato PyPI) |

Nenhum desses valores é sensível; a autenticação é de curta duração via OIDC — **sem
access key fixa**.

### OIDC + IAM

O GitHub Actions assume uma IAM Role via OIDC (`id-token: write`). A trust policy da role
deve confiar no provedor OIDC do GitHub e restringir ao repositório/tag. Permissões:

**Publisher (CI de release):**
```
codeartifact:GetAuthorizationToken
codeartifact:GetRepositoryEndpoint
codeartifact:ReadFromRepository
codeartifact:PublishPackageVersion
sts:GetServiceBearerToken
```

**Consumer (desenvolvedores instalando o pacote):**
```
codeartifact:GetAuthorizationToken
codeartifact:GetRepositoryEndpoint
codeartifact:ReadFromRepository
sts:GetServiceBearerToken
```

---

## Governança de versões

- Versões publicadas são **imutáveis** — **nunca sobrescrever** uma versão existente.
- A remoção de uma versão é **processo manual** (via console/CLI do CodeArtifact),
  feito apenas em caso excepcional e documentado.
- O **rollback** é o fluxo pip padrão: `pip install maes==X.Y.Z`. Não existe mecanismo
  próprio de rollback/update no MAES.

---

## Consumo (referência rápida)

```bash
aws sso login
aws codeartifact login --tool pip --domain <domain> --repository <repository>
pip install maes[all]
maes --version
```

`pip install maes[all]` requer **Python 3.10+** (extra `mcp`). O core (`maes` sem extras)
roda em 3.9+.

---

## Troubleshooting

- **`pip install` não encontra `anthropic`/`mcp`/`pydantic-core`:** falta o **upstream para
  o `pypi.org`** no repositório CodeArtifact (ver acima).
- **Token expirado (401/403):** os tokens do CodeArtifact têm TTL (~12h). Rode novamente
  `aws codeartifact login --tool pip …`. O token do `pip` é separado do token do `twine`.
- **Proxy / TLS corporativo:** se o `pip install` falhar com erros de certificado, configure
  o certificado da empresa (`PIP_CERT`, `REQUESTS_CA_BUNDLE`) ou o proxy (`HTTPS_PROXY`).
- **`mcp` falha em Python 3.9:** use Python 3.10+ para `maes[all]`.
- **Release abortou no guard de versão:** a git tag (`vX.Y.Z`) não coincide com
  `maes.__version__`. Ajuste `maes/__init__.py` ou a tag e refaça.
