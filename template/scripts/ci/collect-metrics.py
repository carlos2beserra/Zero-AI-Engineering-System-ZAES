#!/usr/bin/env python3
"""
MAES Collect Metrics — Coleta métricas de desenvolvimento via GitHub API.

Gera relatório semanal/mensal de métricas de desenvolvimento usando
dados reais do repositório GitHub (sem dependências além da stdlib Python).

Uso:
    python scripts/collect-metrics.py --repo owner/repo --days 7
    python scripts/collect-metrics.py --repo owner/repo --days 30 --output markdown
    python scripts/collect-metrics.py --repo owner/repo --since 2026-05-01

Variáveis de ambiente necessárias:
    GH_TOKEN           — token GitHub com permissão de leitura no repo
    GITHUB_REPOSITORY  — alternativa ao --repo (ex: owner/repo)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ─── GitHub API client mínimo (sem dependências externas) ─────────────────────
class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo  = repo

    def _get(self, path: str, params: dict | None = None) -> list | dict:
        url = f"{self.BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {self.token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            print(f"GitHub API erro {exc.code}: {path}", file=sys.stderr)
            return []

    def get_merged_prs(self, since: datetime) -> list[dict]:
        """Retorna PRs mergeados desde `since`."""
        prs, page = [], 1
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        while True:
            batch = self._get(
                f"/repos/{self.repo}/pulls",
                {"state": "closed", "sort": "updated", "direction": "desc",
                 "per_page": 100, "page": page},
            )
            if not batch:
                break

            for pr in batch:
                if not pr.get("merged_at"):
                    continue
                merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                if merged_at < since.replace(tzinfo=timezone.utc):
                    return prs
                prs.append(pr)

            if len(batch) < 100:
                break
            page += 1

        return prs

    def get_pr_reviews(self, pr_number: int) -> list[dict]:
        return self._get(f"/repos/{self.repo}/pulls/{pr_number}/reviews") or []

    def get_pr_comments(self, pr_number: int) -> list[dict]:
        return self._get(f"/repos/{self.repo}/issues/{pr_number}/comments") or []


# ─── Cálculo de métricas ──────────────────────────────────────────────────────
def calc_cycle_time_hours(pr: dict) -> float | None:
    created = pr.get("created_at")
    merged  = pr.get("merged_at")
    if not (created and merged):
        return None
    t0 = datetime.fromisoformat(created.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(merged.replace("Z", "+00:00"))
    return (t1 - t0).total_seconds() / 3600


def has_maes_task(pr: dict) -> bool:
    """Verifica se o PR referencia uma TASK-NNN."""
    import re
    text = f"{pr.get('title', '')} {pr.get('body', '') or ''}"
    return bool(re.search(r"TASK-\d+", text, re.IGNORECASE))


def count_review_rounds(reviews: list[dict]) -> int:
    """Conta quantas vezes 'CHANGES_REQUESTED' foi emitido (rounds de revisão)."""
    return sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED")


def analyze_pr(pr: dict, client: GitHubClient) -> dict:
    pr_number = pr["number"]
    reviews   = client.get_pr_reviews(pr_number)

    return {
        "number":        pr_number,
        "title":         pr["title"],
        "merged_at":     pr.get("merged_at", ""),
        "cycle_hours":   calc_cycle_time_hours(pr),
        "review_rounds": count_review_rounds(reviews),
        "has_task":      has_maes_task(pr),
        "additions":     pr.get("additions", 0),
        "deletions":     pr.get("deletions", 0),
        "author":        pr.get("user", {}).get("login", "unknown"),
    }


# ─── Formatação de relatório ──────────────────────────────────────────────────
def format_markdown_report(metrics: dict, period_days: int, repo: str) -> str:
    prs       = metrics["prs"]
    n         = len(prs)
    since_str = metrics["since"].strftime("%Y-%m-%d")
    until_str = metrics["until"].strftime("%Y-%m-%d")

    cycle_times   = [p["cycle_hours"] for p in prs if p["cycle_hours"] is not None]
    avg_cycle     = sum(cycle_times) / len(cycle_times) if cycle_times else 0
    avg_reviews   = sum(p["review_rounds"] for p in prs) / n if n else 0
    maes_adoption = sum(1 for p in prs if p["has_task"]) / n * 100 if n else 0
    rework_rate   = sum(1 for p in prs if p["review_rounds"] > 2) / n * 100 if n else 0

    lines = [
        f"# MAES Metrics — {since_str} a {until_str}",
        f"> Repositório: `{repo}` · Período: {period_days} dias",
        "",
        "## Resumo Executivo",
        "",
        f"| Métrica | Valor |",
        "|---|---|",
        f"| PRs mergeados | {n} |",
        f"| Cycle time médio | {avg_cycle:.1f}h |",
        f"| Rounds de revisão médios | {avg_reviews:.1f} |",
        f"| Taxa de adoção MAES (TASK-NNN) | {maes_adoption:.0f}% |",
        f"| Taxa de retrabalho (>2 rounds) | {rework_rate:.0f}% |",
        "",
    ]

    # Velocidade de entrega
    lines += [
        "## Velocidade de Entrega",
        "",
        "| PR | Autor | Cycle Time | Revisões | MAES |",
        "|---|---|---|---|---|",
    ]
    for p in sorted(prs, key=lambda x: x["merged_at"], reverse=True)[:20]:
        cycle_str = f"{p['cycle_hours']:.1f}h" if p["cycle_hours"] else "—"
        maes_str  = "✅" if p["has_task"] else "❌"
        lines.append(
            f"| #{p['number']} {p['title'][:40]}… "
            f"| {p['author']} | {cycle_str} | {p['review_rounds']} | {maes_str} |"
        )

    # Adoção do MAES
    no_task = [p for p in prs if not p["has_task"]]
    if no_task:
        lines += [
            "",
            "## PRs sem Task MAES",
            "",
            "Os PRs abaixo não referenciam uma TASK-NNN:",
            "",
        ]
        for p in no_task:
            lines.append(f"- #{p['number']} [{p['title']}] por @{p['author']}")

    lines += [
        "",
        "---",
        f"_Gerado por MAES Collect Metrics em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
    ]
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAES Collect Metrics — relatório de métricas via GitHub API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--repo",   help="Repositório no formato owner/repo")
    parser.add_argument("--days",   type=int, default=7, help="Dias a analisar (padrão: 7)")
    parser.add_argument("--since",  help="Data inicial no formato YYYY-MM-DD")
    parser.add_argument(
        "--output",
        default="markdown",
        choices=["markdown", "json"],
        help="Formato de saída (padrão: markdown)",
    )
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Erro: variável GH_TOKEN não definida", file=sys.stderr)
        sys.exit(1)

    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("Erro: forneça --repo owner/repo ou defina GITHUB_REPOSITORY", file=sys.stderr)
        sys.exit(1)

    until = datetime.now(timezone.utc)
    since = (
        datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        if args.since
        else until - timedelta(days=args.days)
    )

    print(f"Coletando PRs de {repo} desde {since.strftime('%Y-%m-%d')}...", file=sys.stderr)

    client = GitHubClient(token, repo)
    raw_prs = client.get_merged_prs(since)

    print(f"{len(raw_prs)} PRs mergeados encontrados.", file=sys.stderr)

    analyzed = []
    for i, pr in enumerate(raw_prs, 1):
        print(f"  Analisando PR #{pr['number']} ({i}/{len(raw_prs)})...", file=sys.stderr)
        analyzed.append(analyze_pr(pr, client))

    metrics = {"prs": analyzed, "since": since, "until": until}

    if args.output == "json":
        # Serializa com dates como strings
        output = {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "prs":   analyzed,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_markdown_report(metrics, args.days, repo))


if __name__ == "__main__":
    main()
