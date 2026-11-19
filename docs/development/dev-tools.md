# MAES Dev Tools (`python -m maint`)

Ferramentas internas para **mantenedores do MAES** — automação de desenvolvimento do
próprio framework. **Não** fazem parte da CLI pública (`maes …`) nem são distribuídas.

Vivem em `template/scripts/tools/maint/` (irmão de `maes/` e `tests/`) e são invocadas a
partir de `template/scripts/tools` (mesmo diretório de trabalho dos testes e do CI, onde
`import maes` resolve):

```bash
python -m maint <comando> ...
```

## Princípios (guia para toda ferramenta interna futura)

1. **Exclusivas de mantenedor** — destinam-se a quem desenvolve o MAES, não aos usuários.
2. **Nunca na CLI pública** — não adicionam subcomandos a `maes` nem alteram `maes/__main__.py`.
3. **Nunca distribuídas** — ficam **fora** do pacote `maes` (o glob `include=["maes*"]` do
   `pyproject.toml` não as empacota; o teste de empacotamento verifica o conteúdo do wheel).
4. **Reutilizam APIs do framework** — ex.: `maes.versioning`, `maes.migrations`. Não
   reescrevem lógica que já existe.
5. **Não duplicam regra de negócio** — validação/contratos vêm do próprio framework.
6. **Apenas stdlib** — sem dependências novas; cross-platform (Windows/Linux/macOS).
7. **Determinísticas e reproduzíveis** — mesma entrada ⇒ mesma saída.

## Arquitetura

```
maint/
├── __main__.py        # `python -m maint` → argparse + dispatch (registro explícito)
├── validation.py      # validação (reusa maes.versioning / maes.migrations)
├── paths.py           # derivação de nomes/caminhos
├── templates.py       # render via string.Template
├── templates/
│   └── migration.py.template   # boilerplate + contrato (fonte única)
└── commands/
    └── migration.py   # comando `migration create`
```

Cada comando é um módulo em `commands/` que expõe `register(subparsers)`; o dispatcher
importa e registra explicitamente (sem plugin/discovery). Adicionar um comando = novo módulo
+ um import/registro em `__main__.py`. Módulos de apoio têm responsabilidade explícita
(nada de `_common`/`utils`); criam-se apenas quando um comando precisa.

### Commands × Validators (diretriz)

- **Commands** executam ações (ex.: `migration create`).
- **Validators** apenas verificam estado, read-only (ex. **futuros**: `migration check`,
  `architecture check`, `template validate`) — ainda não implementados.

## Comandos

### `migration create`

Cria um novo módulo de migração seguindo o contrato
([migrations.md](migrations.md)) e a auto-descoberta.

```bash
python -m maint migration create --from 1.1.0 --to 1.2.0 --description "descreva a migração"
```

Faz: valida as versões (reduced SemVer `X.Y.Z` via `maes.versioning`), exige
`--to > --from`, rejeita duplicata contra `maes.migrations.MIGRATIONS`, deriva o nome
`m_1_1_0_to_1_2_0.py`, **recusa sobrescrever** e escreve o boilerplate (com header de
auditoria + `_run` guardado) a partir de `maint/templates/migration.py.template`. O arquivo
gerado é **auto-descoberto** — sem editar registro. Depois, implemente o `_run` seguindo os
**exemplos de padrões de guarda idempotente** em
[migrations.md → Exemplos de `_run`](migrations.md#exemplos-de-_run-padrões-de-guarda-idempotente)
(ou peça para a AI gerar apontando-a para aquele contrato + exemplos).
