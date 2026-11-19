#!/usr/bin/env python3
"""maes blueprint — catálogo determinístico de aplicações homologadas.

Um Blueprint é uma unidade de governança técnica de aplicação homologada
(ver docs/adr/0001). Este módulo NUNCA cria projeto, executa scaffold ou decide
arquitetura — apenas lê o catálogo empacotado, valida metadata e copia contexto.

Comandos:
    list                 catálogo disponível
    show <id>            contrato/resumo canônico (blueprint.yaml) para humanos
    prompt <id>         contexto operacional (prompt.md) para o Agent
    bootstrap <id>      receita de execução (bootstrap.yaml) para o Agent
    seed <id>           materializa context/human/ no projeto (.maes/)
    validate [<id>]     garante integridade do Blueprint

O catálogo vive empacotado no pacote (`templates/blueprints/`), disponível mesmo
sem projeto MAES.
"""

from __future__ import annotations

from pathlib import Path

# ─── Localização do catálogo empacotado ─────────────────────────────────────────

_BLUEPRINTS_DIR = Path(__file__).parent / "templates" / "blueprints"


# ─── Leitura do catálogo ─────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _blueprint_dir(blueprint_id: str) -> Path:
    return _BLUEPRINTS_DIR / blueprint_id


def _manifest_path(blueprint_id: str) -> Path:
    return _blueprint_dir(blueprint_id) / "blueprint.yaml"


def _list_ids() -> list[str]:
    if not _BLUEPRINTS_DIR.exists():
        return []
    ids = [
        d.name
        for d in _BLUEPRINTS_DIR.iterdir()
        if d.is_dir() and (d / "blueprint.yaml").exists()
    ]
    return sorted(ids)


def _load_manifest(blueprint_id: str) -> dict | None:
    path = _manifest_path(blueprint_id)
    if not path.exists():
        return None
    try:
        return _load_yaml(path)
    except Exception as exc:  # noqa: BLE001 — reporta e não derruba o CLI
        print(f"  ✗ {blueprint_id}: blueprint.yaml inválido ({exc})")
        return None


def _summary_lines(manifest: dict) -> list[str]:
    """Normaliza `summary` (bloco de texto ou lista) em linhas de bullet."""
    summary = manifest.get("summary")
    if isinstance(summary, list):
        return [str(s).strip().lstrip("- ").strip() for s in summary if str(s).strip()]
    if isinstance(summary, str):
        out = []
        for raw in summary.splitlines():
            line = raw.strip().lstrip("- ").strip()
            if line:
                out.append(line)
        return out
    return []


# ─── Comandos ────────────────────────────────────────────────────────────────────

def cmd_list() -> int:
    """Apresenta o catálogo de aplicações homologadas (numerado)."""
    ids = _list_ids()
    if not ids:
        print("Nenhum Blueprint disponível no catálogo.")
        return 0

    print("Aplicações homologadas:\n")
    for idx, blueprint_id in enumerate(ids, start=1):
        manifest = _load_manifest(blueprint_id)
        if manifest is None:
            continue
        name = manifest.get("name", blueprint_id)
        print(f"  {idx}. {name}  [{blueprint_id}]")
        stack = ", ".join(_summary_lines(manifest))
        if stack:
            print(f"     {stack}")
    print("\nEscolha uma opção pelo número ou id.")
    return 0


def cmd_show(blueprint_id: str) -> int:
    """Imprime o contrato/resumo canônico de um Blueprint (para humanos)."""
    manifest = _load_manifest(blueprint_id)
    if manifest is None:
        print(f"✗ Blueprint '{blueprint_id}' não encontrado. Rode `maes blueprint list`.")
        return 1

    name = manifest.get("name", blueprint_id)
    print(f"{name}  [{manifest.get('id', blueprint_id)}]")
    if manifest.get("type"):
        print(f"Tipo: {manifest['type']}")
    if manifest.get("version"):
        print(f"Versão: {manifest['version']}")

    lines = _summary_lines(manifest)
    if lines:
        print("\nStack homologada:")
        for line in lines:
            print(f"  - {line}")

    stack = manifest.get("stack") or {}
    pm = stack.get("package_manager")
    if pm:
        print(f"\nPackage manager: {pm}")
    return 0


def cmd_prompt(blueprint_id: str) -> int:
    """Emite prompt.md — contexto operacional consumido pelo Agent."""
    prompt_path = _blueprint_dir(blueprint_id) / "prompt.md"
    if not _manifest_path(blueprint_id).exists():
        print(f"✗ Blueprint '{blueprint_id}' não encontrado. Rode `maes blueprint list`.")
        return 1
    if not prompt_path.exists():
        print(f"✗ Blueprint '{blueprint_id}' não possui prompt.md.")
        return 1
    print(prompt_path.read_text(encoding="utf-8"), end="")
    return 0


def cmd_bootstrap(blueprint_id: str) -> int:
    """Emite bootstrap/bootstrap.yaml — a ÚNICA fonte de execução (Official First).

    O agente /maes-create obtém a receita por aqui (nunca lê o catálogo direto) e
    executa os passos via Bash. O CLI não executa nada.
    """
    bootstrap_path = _blueprint_dir(blueprint_id) / "bootstrap" / "bootstrap.yaml"
    if not _manifest_path(blueprint_id).exists():
        print(f"✗ Blueprint '{blueprint_id}' não encontrado. Rode `maes blueprint list`.")
        return 1
    if not bootstrap_path.exists():
        print(f"✗ Blueprint '{blueprint_id}' não possui bootstrap/bootstrap.yaml.")
        return 1
    print(bootstrap_path.read_text(encoding="utf-8"), end="")
    return 0


def _write_provenance(blueprint_id: str, maes_dir: Path) -> str | None:
    """Registra a proveniência do Blueprint no config.yaml do projeto.

    Escrita determinística pelo **CLI** durante o seed (ADR 0003/0006): o agente
    nunca escreve estado canônico. Idempotente — se um bloco `blueprint:` já existe,
    não reescreve. Preserva o restante do arquivo (inserção textual, não round-trip
    YAML, para manter comentários). É distinto de `meta.maes_version`.

    Campos: `id`, `version`, `created_at`. `organization` (derivação do
    OWNERSHIP.yaml) e `source_hash` (algoritmo/inputs) são decisão futura
    (RFC 0001 §10) — não gravados aqui.

    Retorna a versão registrada, ou None se não havia config.yaml para anotar.
    """
    import re
    from datetime import date

    config_path = maes_dir / "config.yaml"
    if not config_path.exists():
        return None

    text = config_path.read_text(encoding="utf-8")
    if re.search(r"(?m)^blueprint:", text):
        return None  # proveniência já registrada — idempotente

    manifest = _load_manifest(blueprint_id) or {}
    version = str(manifest.get("version", "")).strip()
    block = (
        "\n# Proveniência do Blueprint — escrita pelo CLI no seed (ADR 0003/0006).\n"
        "# Origem histórica do projeto; distinta de meta.maes_version.\n"
        "blueprint:\n"
        f"  id: {blueprint_id}\n"
        f'  version: "{version}"\n'
        f'  created_at: "{date.today().isoformat()}"\n'
    )
    if not text.endswith("\n"):
        text += "\n"
    config_path.write_text(text + block, encoding="utf-8")
    return version


def cmd_seed(blueprint_id: str, maes_dir: Path) -> int:
    """Materializa context/human/ do Blueprint em .maes/context/human/.

    Idempotente. NUNCA toca synthesis/ nem inferred/. Requer projeto (.maes/).
    Ao final, registra a proveniência do Blueprint no config.yaml (determinístico).
    """
    if not _manifest_path(blueprint_id).exists():
        print(f"✗ Blueprint '{blueprint_id}' não encontrado. Rode `maes blueprint list`.")
        return 1

    src_human = _blueprint_dir(blueprint_id) / "context" / "human"
    if not src_human.exists():
        print(f"✗ Blueprint '{blueprint_id}' não possui context/human/.")
        return 1

    import shutil

    dst_human = maes_dir / "context" / "human"
    dst_human.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for src in sorted(src_human.glob("*.md")):
        dst = dst_human / src.name
        shutil.copy2(src, dst)
        copied.append(src.name)

    if not copied:
        print(f"⚠ Nenhum arquivo .md em context/human/ do Blueprint '{blueprint_id}'.")
        return 0

    print(f"✓ Contexto organizacional semeado em .maes/context/human/ ({len(copied)} arquivos):")
    for name in copied:
        print(f"    + {name}")

    recorded = _write_provenance(blueprint_id, maes_dir)
    if recorded is not None:
        print(f"✓ Proveniência registrada em config.yaml (blueprint '{blueprint_id}' v{recorded}).")

    print("\nPróximo passo: `maes sync` para compilar o contexto.")
    return 0


def _validate_manifest(manifest: dict, errors: list[str]) -> None:
    required = ["id", "name", "type", "version", "summary", "stack", "seed_human"]
    for field in required:
        if field not in manifest or manifest.get(field) in (None, "", []):
            errors.append(f"blueprint.yaml: campo obrigatório ausente ou vazio: '{field}'")
    stack = manifest.get("stack")
    if stack is not None and not isinstance(stack, dict):
        errors.append("blueprint.yaml: 'stack' deve ser um mapa (languages/frameworks/package_manager)")


def _validate_one(blueprint_id: str) -> list[str]:
    """Retorna a lista de erros (vazia = Blueprint íntegro)."""
    errors: list[str] = []
    bp_dir = _blueprint_dir(blueprint_id)

    manifest = _load_manifest(blueprint_id)
    if manifest is None:
        return ["blueprint.yaml ausente ou inválido"]

    _validate_manifest(manifest, errors)

    prompt_path = bp_dir / "prompt.md"
    if not prompt_path.exists() or not prompt_path.read_text(encoding="utf-8").strip():
        errors.append("prompt.md ausente ou vazio")

    if not (bp_dir / "bootstrap" / "bootstrap.yaml").exists():
        errors.append("bootstrap/bootstrap.yaml ausente")

    if manifest.get("seed_human") is True:
        human_dir = bp_dir / "context" / "human"
        if not human_dir.exists() or not any(human_dir.glob("*.md")):
            errors.append("context/human/ ausente ou vazio (exigido quando seed_human=true)")

    return errors


def cmd_validate(blueprint_id: str | None = None) -> int:
    """Valida a integridade de um Blueprint (ou de todos)."""
    ids = [blueprint_id] if blueprint_id else _list_ids()
    if not ids:
        print("Nenhum Blueprint para validar.")
        return 0
    if blueprint_id and not _manifest_path(blueprint_id).exists():
        print(f"✗ Blueprint '{blueprint_id}' não encontrado. Rode `maes blueprint list`.")
        return 1

    total_errors = 0
    for bid in ids:
        errors = _validate_one(bid)
        if errors:
            total_errors += len(errors)
            print(f"✗ {bid}:")
            for err in errors:
                print(f"    - {err}")
        else:
            print(f"✓ {bid}: íntegro")

    return 1 if total_errors else 0
