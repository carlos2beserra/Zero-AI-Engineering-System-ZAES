# MAES — Guia de Migrações (`maes upgrade`)

Este documento formaliza o **contrato das migrações** do MAES e explica como o
`maes upgrade` migra o `.maes/` de um projeto existente. O mecanismo é deliberadamente
simples — no espírito de Alembic/Flyway/Rails/Django, mas sem banco de histórico: o MAES
guarda apenas a **versão atual** do projeto e re-deriva o caminho a cada upgrade.

## Pipeline do `maes upgrade`

```
Projeto (.maes/)
      │
      ▼
read_project_version()   ── config.yaml inválido ─► ProjectConfigError → abort (exit ≠ 0)
      │                     (config ausente → 0.0.0 = projeto novo; sem meta → 0.0.0 = pré-versionamento)
      ▼
find_path(current, target)   seleção idempotente, tolerante a gaps
      │
      ▼
apply migrations          cada m.run(maes_dir) é guardada; 1ª falha → abort, versão NÃO carimbada
      │
      ▼
write_project_version()   carimba meta.maes_version SÓ após sucesso de todas as migrações
      │
      ▼
sync                      recompila contexto + adapters (pulado com --skip-sync)
```

`target` é sempre a versão do CLI instalado (`maes.__version__`). A versão do projeto vive
em `.maes/config.yaml` → `meta.maes_version`.

## Contrato de versão (`meta.maes_version`)

`meta.maes_version` usa um **SemVer reduzido**: somente o formato `X.Y.Z` (exatamente três
inteiros) faz parte do contrato do MAES. Formatos como `1`, `1.0`, `1.0-beta` ou
`1.0.0+build` **não** são suportados. `versioning.version_tuple()` mapeia qualquer entrada
fora do contrato para `(0, 0, 0)` (tratada como "mais antiga"), evitando desordenação
silenciosa.

## Config ausente vs. config corrompido

| Estado do `.maes/config.yaml` | Interpretação | `maes upgrade` |
|---|---|---|
| **ausente** | projeto novo | versão `0.0.0` (roda a cadeia completa) |
| presente, válido, **sem** `meta.maes_version` | pré-versionamento (legítimo) | versão `0.0.0` |
| presente, válido, com `meta.maes_version` | projeto versionado | usa o valor |
| **presente, mas ilegível / YAML inválido / topo não-mapa** | **corrupção** | **aborta com `ProjectConfigError`, exit ≠ 0, nenhuma migração** |

Corrupção **nunca** é tratada como projeto novo (evita reaplicar migrações destrutivas
sobre um projeto que na verdade está avançado). Recuperação: `.maes/` é versionado em git —
use `git checkout -- .maes` para restaurar `config.yaml`/`agents/`.

## Estratégia de seleção — `find_path(current, target)`

O algoritmo percorre as migrações **ordenadas por `from_version`** e inclui cada `m` se
`from_version >= cursor` e `to_version <= target`, avançando o cursor para `to_version`.

- **Por que funciona / premissa:** as migrações são **idempotentes e guardadas**. Aplicar
  uma migração cujo `from_version` o projeto tecnicamente "pulou" (gap) é **inócuo**, porque
  a migração verifica o estado antes de agir. Por isso o `>=` (em vez de `==`) é seguro e
  **gaps entre versões são suportados** sem exigir uma cadeia contígua.
- **Por que não precisa de histórico:** como cada migração é reexecutável e a versão só é
  carimbada após sucesso total, uma reexecução (inclusive após falha parcial) simplesmente
  reaplica as migrações — as guardas transformam as já aplicadas em no-ops. Não é preciso um
  ledger de "quais migrações rodaram" (padrão mais simples que Flyway/Alembic, adequado ao
  volume de migrações do MAES).

## Contrato de uma migração

Uma migração **deve** ser:

- **idempotente** — guardar por existência/estado; reexecutar não causa efeito adicional;
- **determinística** — mesma entrada ⇒ mesma saída;
- **reexecutável** — segura para rodar múltiplas vezes (inclusive após falha parcial);
- **independente da origem da instalação** — igual em editable / wheel / CodeArtifact;
- **compatível com gaps de versão** — não assumir que o projeto passou por versões intermediárias.

Uma migração **não pode**:

- depender de internet ou de APIs externas;
- depender do relógio do sistema;
- depender da ordem do sistema de arquivos / do SO;
- solicitar interação do usuário;
- sobrescrever arquivos modificados pelo usuário **sem guarda apropriada**;
- introduzir qualquer comportamento não determinístico.

## Como escrever uma nova migração

1. **Gere o esqueleto** com a dev-tool (recomendado — ver [dev-tools.md](dev-tools.md)):

   ```bash
   # a partir de template/scripts/tools
   python -m maint migration create --from 1.1.0 --to 1.2.0 --description "o que ela faz"
   ```

   Isso valida as versões, deriva o nome `m_1_1_0_to_1_2_0.py`, recusa sobrescrever e cria
   o arquivo com o header de auditoria, o contrato e um `_run` guardado que lança
   `NotImplementedError` (marcador do que falta implementar). Alternativa manual: criar
   `maes/migrations/m_<from>_to_<to>.py` (`from`/`to` em `X_Y_Z`) com a mesma forma.

2. **Implemente o `_run`** de forma **guardada e idempotente** (veja os exemplos abaixo) e
   ajuste a `description`. Estrutura mínima:

   ```python
   from pathlib import Path
   from maes.migrations import Migration

   def _run(maes_dir: Path) -> None:
       ...  # transformação guardada e idempotente

   MIGRATION = Migration(
       from_version="1.1.0", to_version="1.2.0",
       description="...", run=_run,
   )
   ```

3. **Não** edite `_load_migrations()`: os módulos `m_*.py` são **auto-descobertos** via
   `pkgutil.iter_modules` e ordenados por `from_version`. Um módulo `m_*.py` que não exporte
   `MIGRATION` falha explicitamente no carregamento.

> Você também pode **pedir para a AI gerar o `_run`** — aponte-a para este contrato e para
> os exemplos abaixo, e depois revise contra o checklist. A regra de ouro é a **guarda**:
> a migração deve checar o estado antes de mudar, para ser um no-op quando já aplicada.

### Exemplos de `_run` (padrões de guarda idempotente)

Todos os exemplos abaixo derivam de migrações reais em
[`maes/migrations/`](../../template/scripts/tools/maes/migrations/) — leia os arquivos
`m_*.py` para as versões completas.

**a) Adicionar/ajustar um campo no `config.yaml` (YAML)** — guarda por presença
(baseado em `m_0_0_0_to_0_1_0.py`):

```python
def _run(maes_dir: Path) -> None:
    config = maes_dir / "config.yaml"
    if not config.exists():
        return
    text = config.read_text(encoding="utf-8")
    if "telemetry:" in text:            # guarda: já aplicado → no-op
        return
    config.write_text(text + "\ntelemetry:\n  enabled: false\n", encoding="utf-8")
```

**b) Adicionar um campo a cada entrada de `synthesis/assertions.json` (JSON)** — guarda por
entrada (baseado em `m_0_12_3_to_0_13_0.py`):

```python
def _run(maes_dir: Path) -> None:
    import json
    path = maes_dir / "synthesis" / "assertions.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for entry in data.get("assertions", []):
        if "owner_context" not in entry:      # guarda por entrada
            entry["owner_context"] = None
            changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

**c) Renomear um agent e limpar adapters obsoletos** — guarda por existência
(baseado em `m_0_8_0_to_0_9_0.py`):

```python
def _run(maes_dir: Path) -> None:
    agents = maes_dir / "agents"
    old, new = agents / "old-id.agent.yaml", agents / "new-id.agent.yaml"
    if not old.exists():                  # guarda: já renomeado (ou inexistente) → no-op
        return
    new.write_text(old.read_text(encoding="utf-8").replace("id: old-id", "id: new-id"),
                   encoding="utf-8")
    old.unlink()
    # Remova só os adapters GERADOS do id antigo; NÃO escreva os novos à mão — o passo de
    # `sync` (após as migrações) recompila os adapters de todos os agents para as IAs.
    (maes_dir.parent / ".claude" / "commands" / "old-id.md").unlink(missing_ok=True)
```

> **Não gere arquivos de adapter (`.claude/commands/…`, `.cursor/rules/…`, skills) na
> migração.** A migração mexe só no estado-fonte em `.maes/` (config, agents, synthesis); o
> `sync` que roda ao final do `maes upgrade` recompila os adapters para todas as IAs
> configuradas. Migrações que renomeiam/removem agents só precisam **limpar** os arquivos
> gerados obsoletos.

### Checklist de PR

- [ ] Nome do arquivo `m_<X_Y_Z>_to_<A_B_C>.py`; `from_version`/`to_version` em `X.Y.Z`.
- [ ] `_run` é guardada e idempotente (rodar 2× não muda o resultado).
- [ ] Sem rede, relógio, aleatoriedade, ordem de FS ou interação.
- [ ] Não sobrescreve arquivo do usuário sem guarda.
- [ ] Teste cobrindo aplicação **e** reexecução (idempotência).
- [ ] **Contrato público alterado?** Se o PR muda schema de artefato emitido, semântica de campo
      existente, comportamento observacional ou arquivo derivado consumido por agentes: a avaliação
      de impacto no upgrade foi feita e **a conclusão está registrada** — inclusive quando for "não
      exige migração". Ver a regra abaixo.

## Compatibilidade é responsabilidade do upgrade

O usuário **nunca** deve precisar saber quais artefatos mudaram entre versões do MAES. Sempre que uma
nova versão alterar contrato observacional, schema ou arquivo derivado, o mecanismo oficial de upgrade
encapsula toda a compatibilidade necessária. Release note descreve o que mudou; ela **não** é onde o
usuário descobre o que precisa consertar à mão.

> Toda alteração que modifique contrato público do Analyze — schema de artefato emitido, semântica de
> campo existente, comportamento observacional ou arquivo derivado consumido por agentes — deve,
> **durante o planejamento**, avaliar explicitamente se exige extensão do fluxo de `maes upgrade`, e
> registrar a conclusão (inclusive quando a conclusão for "não exige"). Planos que alteram esses
> contratos sem essa avaliação estão incompletos.

Critério de aceite de qualquer evolução desse tipo: um repositório configurado em versão anterior,
após executar **apenas** o fluxo oficial (`maes upgrade` e os comandos subsequentes documentados),
passa a utilizar integralmente a nova implementação — sem intervenção manual no repositório e sem
conhecer nenhum detalhe interno da evolução. Precedente e roteiro de validação:
[ADR 0009](../adr/0009-observacao-exige-populacao-conhecida.md) e
[findings-discovery-sampling-e-placement-confidence.md](findings-discovery-sampling-e-placement-confidence.md).
