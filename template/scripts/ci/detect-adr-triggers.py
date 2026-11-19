#!/usr/bin/env python3
"""
MAES Detect ADR Triggers — Detecta mudanças que exigem registro de decisão arquitetural.

Analisa o diff de um PR e identifica padrões que indicam mudanças arquiteturais
significativas (schema, contratos de API, dependências de infra, arquitetura MAES).

Uso:
    # Diff via stdin
    git diff origin/main...HEAD | python scripts/detect-adr-triggers.py --stdin

    # Diff via arquivo
    python scripts/detect-adr-triggers.py --diff pr.diff

    # Lista de arquivos modificados (sem conteúdo do diff)
    python scripts/detect-adr-triggers.py --files file1.sql file2.yaml

Saída:
    JSON: { "triggers": [{ "type": "...", "file": "...", "description": "..." }] }

Exit codes:
    0  — nenhum trigger encontrado
    1  — triggers encontrados (sugere registro de ADR)
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ─── Definições de triggers ──────────────────────────────────────────────────

TRIGGERS: list[dict] = [
    {
        "type": "api-contract-change",
        "description": "Contrato de API modificado — considere registrar impacto em consumers",
        "file_patterns": [
            r".*\.openapi\.ya?ml$",
            r".*/openapi\.ya?ml$",
            r".*/swagger\.json$",
            r".*/openapi\.json$",
            r".*\.proto$",
            r".*/contracts/.*",
            r".*/proto/.*",
            r".*/api-contracts/.*",
        ],
        "diff_patterns": [],
    },
    {
        "type": "schema-change",
        "description": "Migration de banco com mudança destrutiva ou obrigatória",
        "file_patterns": [
            r".*/db/migrations/.*\.sql$",
            r".*/migrations/.*\.sql$",
            r".*\d{4}_.*\.sql$",
            r".*schema\.prisma$",
            r".*/prisma/schema\.prisma$",
        ],
        "diff_patterns": [
            r"ALTER\s+TABLE",
            r"DROP\s+COLUMN",
            r"ADD\s+COLUMN\s+\w+\s+\w+\s+NOT\s+NULL",
            r"DROP\s+TABLE",
            r"RENAME\s+TABLE",
            r"RENAME\s+COLUMN",
        ],
    },
    {
        "type": "infra-dependency",
        "description": "Nova dependência de infraestrutura adicionada",
        "file_patterns": [
            r".*/package\.json$",
            r".*/go\.mod$",
            r".*/requirements\.txt$",
            r".*/pyproject\.toml$",
            r".*/pom\.xml$",
            r".*/build\.gradle$",
            r".*/Gemfile$",
            r".*/Cargo\.toml$",
        ],
        "diff_patterns": [
            # Detecta linhas adicionadas com dependências de infra conhecidas
            r'^\+.*"?(redis|kafka|rabbitmq|elasticsearch|mongodb|cassandra|'
            r'grpc|graphql|prisma|typeorm|sequelize|sqlalchemy|hibernate|'
            r'aws-sdk|@aws-sdk|azure-|google-cloud-|firebase-|stripe|twilio|'
            r'sendgrid|datadog|sentry|newrelic|opentelemetry)"?',
        ],
    },
    {
        "type": "maes-context-architecture",
        "description": "Arquivo de contexto MAES modificado",
        "file_patterns": [
            r"\.maes/context/human/decisions\.md$",
            r"\.maes/context/human/principles\.md$",
        ],
        "diff_patterns": [],
    },
    {
        "type": "auth-change",
        "description": "Mudança em autenticação ou autorização",
        "file_patterns": [
            r".*/auth/.*",
            r".*/middleware/auth.*",
            r".*auth.*middleware.*",
            r".*/guards?/.*",
            r".*/permissions?/.*",
            r".*/roles?/.*",
        ],
        "diff_patterns": [],
    },
]


# ─── Lógica de detecção ───────────────────────────────────────────────────────

def extract_files_from_diff(diff: str) -> list[str]:
    """Extrai os nomes de arquivo do diff."""
    return re.findall(r"^(?:\+\+\+|---)\s+(?:a/|b/)?(.+)$", diff, re.MULTILINE)


def check_trigger(trigger: dict, files: list[str], diff: str) -> list[dict]:
    """Verifica se um trigger foi ativado. Retorna lista de matches."""
    matches = []
    file_regexes = [re.compile(p, re.IGNORECASE) for p in trigger["file_patterns"]]
    diff_regexes = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in trigger.get("diff_patterns", [])]

    for f in files:
        if f in ("/dev/null", ""):
            continue

        file_matched = any(rx.search(f) for rx in file_regexes)
        if not file_matched:
            continue

        # Se não há diff_patterns, o arquivo modificado já é suficiente
        if not diff_regexes:
            matches.append({
                "type":        trigger["type"],
                "file":        f,
                "description": trigger["description"],
            })
            continue

        # Extrai o hunk do diff relativo a este arquivo
        file_section = _extract_file_section(diff, f)
        if any(rx.search(file_section) for rx in diff_regexes):
            matches.append({
                "type":        trigger["type"],
                "file":        f,
                "description": trigger["description"],
            })

    return matches


def _extract_file_section(diff: str, filename: str) -> str:
    """Extrai a seção do diff relativa a um arquivo específico."""
    # Tenta encontrar o bloco do diff para este arquivo
    escaped = re.escape(filename)
    match = re.search(
        rf"^diff --git.*{escaped}.*$(.+?)(?=^diff --git|\Z)",
        diff,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else diff


def detect_triggers(diff: str, extra_files: list[str] | None = None) -> list[dict]:
    files = extract_files_from_diff(diff)
    if extra_files:
        files = list(set(files + extra_files))

    # Remove duplicatas e entradas inválidas
    files = list({f for f in files if f and f != "/dev/null"})

    found: list[dict] = []
    seen: set[tuple] = set()  # (type, file) para deduplicar

    for trigger in TRIGGERS:
        for match in check_trigger(trigger, files, diff):
            key = (match["type"], match["file"])
            if key not in seen:
                seen.add(key)
                found.append(match)

    return found


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAES Detect ADR Triggers — detecta mudanças que exigem registro de decisão",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff",  help="Arquivo .diff do PR")
    source.add_argument("--stdin", action="store_true", help="Ler diff do stdin")
    source.add_argument("--files", nargs="+", help="Lista de arquivos modificados (sem diff)")
    args = parser.parse_args()

    if args.stdin:
        diff = sys.stdin.read()
        extra = None
    elif args.diff:
        diff = Path(args.diff).read_text(encoding="utf-8")
        extra = None
    else:
        # Apenas lista de arquivos — sem diff para análise de conteúdo
        diff = ""
        extra = args.files

    triggers = detect_triggers(diff, extra)

    print(json.dumps({"triggers": triggers}, ensure_ascii=False, indent=2))

    sys.exit(1 if triggers else 0)


if __name__ == "__main__":
    main()
