#!/usr/bin/env python3
"""
MAES Eval PR — LLM-as-judge para avaliação automática de PRs.

Usa o rubric de .maes/evals/eval-rules.md para avaliar o diff de um PR
e retorna scores + comentário formatado para postar no GitHub.

Uso:
    python scripts/eval-pr.py --diff pr.diff --task .maes/tasks/TASK-042.md
    python scripts/eval-pr.py --diff pr.diff                        # sem task file
    git diff origin/main...HEAD | python scripts/eval-pr.py --stdin # via stdin

Saída:
    JSON com scores + bloco de comentário markdown
    Use --post-to-github para postar diretamente no PR
    Use --save-result eval-result.json para persistir resultado + uso de tokens

Variáveis de ambiente necessárias:
    ANTHROPIC_API_KEY      — chave Anthropic (provider padrão)
    GITHUB_TOKEN           — GitHub Models / Copilot (provider alternativo)
    GEMINI_API_KEY         — Google Gemini (provider alternativo)
    MAES_PROVIDER          — força um provider: anthropic | github | gemini
    GH_TOKEN               — token GitHub (somente se --post-to-github)
    GITHUB_REPOSITORY      — ex: owner/repo (somente se --post-to-github)
    PR_NUMBER              — número do PR (somente se --post-to-github)
    MAES_EVAL_MODEL        — modelo a usar (padrão por provider)
    MAES_EVAL_BLOCK_ON_POOR — se "true", exit code 1 para veredito poor (padrão: false)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ─── Configuração ─────────────────────────────────────────────────────────────
MAES_ROOT      = Path(__file__).parent.parent
RUBRIC_PATH    = MAES_ROOT / ".maes" / "evals" / "eval-rules.md"
DEFAULT_MODEL  = "claude-sonnet-4-6"
MAX_DIFF_CHARS = 32_000  # ~8k tokens — trunca diffs muito grandes


# ─── Prompts ──────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
Você é um avaliador de código especializado no framework MAES (Maxxi AI Engineering System).
Avalia diffs de Pull Requests usando um rubric estruturado e retorna scores precisos.
Responda SOMENTE com JSON válido no formato especificado. Nenhum texto fora do JSON.\
"""

# Parte estável: carregada com cache_control para reutilização entre PRs do mesmo workflow run
EVAL_CONTEXT_TEMPLATE = """\
RUBRIC DE AVALIAÇÃO MAES:
{rubric}

---

TASK DE REFERÊNCIA:
{task}

---\
"""

# Parte volátil: diff muda a cada PR
EVAL_INSTRUCTION = """\

DIFF DO PR:
```diff
{diff}
```

---

INSTRUÇÃO:
Avalie o diff acima usando o rubric fornecido.

Retorne exatamente este JSON (sem texto fora dele):
{{
  "scores": {{
    "correctness":       <inteiro 0-3>,
    "pattern_adherence": <inteiro 0-3>,
    "security":          <inteiro 0-3>,
    "completeness":      <inteiro 0-3>,
    "cost_efficiency":   <inteiro 0-2>
  }},
  "total":    <soma dos scores, inteiro 0-14>,
  "verdict":  "excellent" | "good" | "regular" | "poor",
  "blockers": ["<problema bloqueante>" ...],
  "notes":    ["<observação relevante>" ...],
  "summary":  "<resumo em 2-3 frases>"
}}

Critérios de verdict:
- excellent: 12-14 pontos
- good:       9-11 pontos
- regular:    6-8  pontos
- poor:       0-5  pontos\
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def load_rubric() -> str:
    rubric = load_text(RUBRIC_PATH)
    if rubric:
        return rubric
    # Fallback mínimo se o arquivo não existir no projeto
    return (
        "Avalie nas dimensões: Correctness (0-3), Pattern Adherence (0-3), "
        "Security (0-3), Completeness (0-3), Cost-Efficiency (0-2). "
        "Seja criterioso e objetivo."
    )


def truncate_diff(diff: str) -> str:
    if len(diff) <= MAX_DIFF_CHARS:
        return diff
    return (
        diff[:MAX_DIFF_CHARS]
        + "\n\n[... diff truncado: muito grande para avaliação completa ...]"
    )


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Tenta extrair JSON se o modelo devolver texto ao redor
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Resposta não é JSON válido:\n{raw}")


def format_github_comment(result: dict) -> str:
    scores  = result["scores"]
    total   = result["total"]
    verdict = result.get("verdict", "poor")
    meta    = result.get("_meta", {})

    emoji = {"excellent": "✅", "good": "🟡", "regular": "🟠", "poor": "🔴"}.get(verdict, "❓")
    label = {"excellent": "EXCELENTE", "good": "BOM", "regular": "REGULAR", "poor": "INSUFICIENTE"}.get(verdict, verdict.upper())

    lines = [
        "### 🎯 Avaliação de Qualidade",
        "",
        f"**{emoji} {label}** &nbsp;·&nbsp; **{total} / 14 pontos**",
        "",
        "| Dimensão | Score | Máx |",
        "|---|:---:|:---:|",
        f"| Corretude | {scores['correctness']} | 3 |",
        f"| Aderência aos padrões | {scores['pattern_adherence']} | 3 |",
        f"| Segurança | {scores['security']} | 3 |",
        f"| Completude | {scores['completeness']} | 3 |",
        f"| Eficiência de contexto | {scores['cost_efficiency']} | 2 |",
        "",
        f"**Resumo:** {result.get('summary', '')}",
    ]

    blockers = result.get("blockers", [])
    if blockers:
        lines += ["", "**🔴 Bloqueantes:**"]
        lines += [f"- {b}" for b in blockers]

    notes = result.get("notes", [])
    if notes:
        lines += ["", "**Observações:**"]
        lines += [f"- {n}" for n in notes]

    if meta:
        input_tokens  = meta.get("input_tokens", 0)
        output_tokens = meta.get("output_tokens", 0)
        cache_read    = meta.get("cache_read_input_tokens", 0)
        model_id      = meta.get("model", DEFAULT_MODEL)
        cost_usd      = _estimate_cost(input_tokens, output_tokens, model_id)
        cost_str      = f"${cost_usd:.4f} USD" if cost_usd > 0 else "N/A"
        lines += [
            "",
            "<details><summary>📊 Tokens</summary>",
            "",
            "| | Tokens |",
            "|---|:---:|",
            f"| Input | {input_tokens:,} |",
            f"| Output | {output_tokens:,} |",
            f"| Cache read | {cache_read:,} |",
            f"| Custo estimado | {cost_str} |",
            "",
            "</details>",
        ]

    provider_label = meta.get("provider", "LLM").capitalize() if meta else "LLM"
    lines += [
        "",
        "---",
        f"_Gerado pelo MAES Eval (rubric: `.maes/evals/eval-rules.md`) · LLM-as-judge via {provider_label} API_",
    ]
    return "\n".join(lines)


_TOKEN_PRICES: dict[str, tuple[float, float]] = {
    # (input $/M tokens, output $/M tokens)
    # Anthropic
    "claude-sonnet-4-6":         (3.0,   15.0),
    "claude-haiku-4-5":          (0.25,   1.25),
    "claude-haiku-4-5-20251001": (0.25,   1.25),
    "claude-opus-4-7":           (15.0,  75.0),
    # OpenAI (GitHub Models)
    "gpt-4o":                    (2.5,   10.0),
    "gpt-4o-mini":               (0.15,   0.60),
    # Gemini
    "gemini-2.0-flash":          (0.075,  0.30),
    "gemini-2.5-pro":            (1.25,  10.0),
}
_DEFAULT_PRICE = (3.0, 15.0)


def _estimate_cost(input_tokens: int, output_tokens: int, model_id: str) -> float:
    price_in, price_out = _TOKEN_PRICES.get(model_id, _DEFAULT_PRICE)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def post_github_comment(comment: str, pr_number: str, repo: str, token: str) -> bool:
    sys.path.insert(0, str(Path(__file__).parent))
    from pr_comment import upsert_pr_comment
    return upsert_pr_comment(pr_number, "eval", comment, repo, token)


# ─── Main helpers ─────────────────────────────────────────────────────────────

def _load_diff(args: argparse.Namespace) -> str:
    if args.stdin:
        diff = sys.stdin.read()
    elif args.diff:
        diff = load_text(args.diff)
    else:
        print("Erro: forneça --diff <arquivo> ou use --stdin", file=sys.stderr)
        sys.exit(1)
    if not diff.strip():
        print("Erro: diff está vazio", file=sys.stderr)
        sys.exit(1)
    return truncate_diff(diff)


def _write_step_summary(result: dict) -> None:
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not step_summary:
        return
    meta     = result.get("_meta", {})
    model    = meta.get("model", DEFAULT_MODEL)
    cost_usd = _estimate_cost(
        meta.get("input_tokens", 0),
        meta.get("output_tokens", 0),
        model,
    )
    cost_str = f"${cost_usd:.4f} USD" if cost_usd > 0 else "N/A"
    with open(step_summary, "a", encoding="utf-8") as f:
        f.write(f"\n### MAES Eval — PR #{meta.get('pr', '?')}\n")
        f.write(f"- **Score:** {result.get('total', 0)}/14 ({result.get('verdict', 'unknown')})\n")
        f.write(f"- **Provider:** {meta.get('provider', 'unknown')} / {model}\n")
        f.write(f"- **Tokens:** {meta.get('input_tokens', 0)} in / {meta.get('output_tokens', 0)} out\n")
        f.write(f"- **Custo estimado:** {cost_str}\n")


def _save_and_output(result: dict, comment: str, args: argparse.Namespace) -> None:
    if args.save_result:
        import pathlib
        pathlib.Path(args.save_result).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Resultado salvo em {args.save_result}", file=sys.stderr)

    if args.output in ("json", "both"):
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output in ("comment", "both"):
        if args.output == "both":
            print("\n---GITHUB-COMMENT---\n")
        print(comment)


def _post_if_requested(comment: str, args: argparse.Namespace) -> None:
    if not args.post_to_github:
        return
    token  = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo   = os.environ.get("GITHUB_REPOSITORY")
    pr_num = os.environ.get("PR_NUMBER")

    if not all([token, repo, pr_num]):
        print(
            "Erro: --post-to-github requer GH_TOKEN, GITHUB_REPOSITORY e PR_NUMBER",
            file=sys.stderr,
        )
        sys.exit(1)

    ok = post_github_comment(comment, pr_num, repo, token)
    if not ok:
        sys.exit(1)
    print("Comentário postado com sucesso", file=sys.stderr)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAES Eval PR — avalia diffs com LLM-as-judge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--diff",  help="Arquivo .diff do PR")
    parser.add_argument("--task",  help="Task file de referência (TASK-NNN.md)")
    parser.add_argument("--stdin", action="store_true", help="Ler diff do stdin")
    parser.add_argument(
        "--output",
        default="both",
        choices=["json", "comment", "both"],
        help="Formato de saída (padrão: both)",
    )
    parser.add_argument(
        "--post-to-github",
        action="store_true",
        help="Postar comentário diretamente no PR (requer GH_TOKEN, GITHUB_REPOSITORY, PR_NUMBER)",
    )
    parser.add_argument(
        "--save-result",
        metavar="FILE",
        help="Salvar resultado completo (scores + tokens) em arquivo JSON (ex: eval-result.json)",
    )
    parser.add_argument(
        "--context-files",
        nargs="*",
        metavar="FILE",
        help="Arquivos de contexto MAES usados nesta avaliação (para correlação de qualidade)",
    )
    args = parser.parse_args()

    diff   = _load_diff(args)
    rubric = load_rubric()
    task   = load_text(args.task) if args.task else "Task não fornecida — avalie com base no diff apenas."

    sys.path.insert(0, str(Path(__file__).parent))
    from _provider import has_any_provider, make_client

    if not has_any_provider():
        print("Nenhum provider LLM configurado — pulando eval de PR", file=sys.stderr)
        sys.exit(0)

    client = make_client(model_env="MAES_EVAL_MODEL")

    try:
        resp = client.create_cached(
            SYSTEM_PROMPT,
            EVAL_CONTEXT_TEMPLATE.format(rubric=rubric, task=task),
            EVAL_INSTRUCTION.format(diff=diff),
            1024,
        )
    except Exception as exc:
        print(f"Erro na API: {exc}", file=sys.stderr)
        sys.exit(1)

    raw = resp.text

    try:
        result = parse_json_response(raw)
    except ValueError as exc:
        print(f"Erro ao parsear resposta: {exc}", file=sys.stderr)
        sys.exit(1)

    pr_number = os.environ.get("PR_NUMBER", "")
    result["_meta"] = {
        "pr":                          int(pr_number) if pr_number.isdigit() else pr_number,
        "model":                       client.model,
        "provider":                    client.provider,
        "input_tokens":                resp.input_tokens,
        "output_tokens":               resp.output_tokens,
        "cache_creation_input_tokens": resp.cache_creation_input_tokens,
        "cache_read_input_tokens":     resp.cache_read_input_tokens,
        "context_files":               args.context_files or [],
        "evaluated_at":                __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    comment = format_github_comment(result)
    _write_step_summary(result)
    _save_and_output(result, comment, args)
    _post_if_requested(comment, args)

    block_on_poor = os.environ.get("MAES_EVAL_BLOCK_ON_POOR", "false").lower() == "true"
    exit_codes = {"excellent": 0, "good": 0, "regular": 0, "poor": 1 if block_on_poor else 0}
    sys.exit(exit_codes.get(result.get("verdict", "poor"), 1 if block_on_poor else 0))


if __name__ == "__main__":
    main()
