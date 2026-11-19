#!/usr/bin/env python3
"""
Upsert a named section in the unified MAES PR review comment.

All CI scripts that post PR comments call this module so the bot produces
a single comment instead of four separate ones.

Usage (CLI):
  python scripts/ci/pr_comment.py --pr PR_NUMBER --section SECTION --content-file FILE

Sections: eval | checklist | adr | context

Environment variables:
  GH_TOKEN / GITHUB_TOKEN   GitHub API token (required)
  GITHUB_REPOSITORY         owner/repo        (required)
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

COMMENT_MARKER = "<!-- maes-pr-review -->"
_SECTION_START = "<!-- maes-section:{name} -->"
_SECTION_END   = "<!-- /maes-section:{name} -->"


# ─── GitHub API helpers ───────────────────────────────────────────────────────

def _api(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _find_maes_comment(pr_number: str, repo: str, token: str) -> tuple[str | None, str | None]:
    """Return (comment_id, body) for the existing unified MAES comment, or (None, None)."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    status, data = _api("GET", url, token)
    if status != 200:
        print(f"Aviso: erro ao listar comentários ({status})", file=sys.stderr)
        return None, None
    for comment in json.loads(data):
        if COMMENT_MARKER in comment.get("body", ""):
            return str(comment["id"]), comment["body"]
    return None, None


# ─── Section management ───────────────────────────────────────────────────────

def _wrap_section(name: str, content: str) -> str:
    start = _SECTION_START.format(name=name)
    end   = _SECTION_END.format(name=name)
    return f"{start}\n{content}\n{end}"


def _replace_section(body: str, name: str, content: str) -> str:
    start   = re.escape(_SECTION_START.format(name=name))
    end     = re.escape(_SECTION_END.format(name=name))
    pattern = rf"{start}.*?{end}"
    wrapped = _wrap_section(name, content)
    if re.search(pattern, body, re.DOTALL):
        return re.sub(pattern, wrapped, body, flags=re.DOTALL)
    return body.rstrip() + "\n\n" + wrapped


def _new_comment(name: str, content: str) -> str:
    return f"{COMMENT_MARKER}\n## 🤖 MAES PR Review\n\n{_wrap_section(name, content)}"


# ─── Public API ───────────────────────────────────────────────────────────────

def upsert_pr_comment(pr_number: str, section: str, content: str, repo: str, token: str) -> bool:
    """
    Insert or update a named section in the unified MAES PR review comment.
    Creates the comment (POST) if it doesn't exist; updates it (PATCH) if it does.
    """
    comment_id, existing_body = _find_maes_comment(pr_number, repo, token)

    if comment_id and existing_body:
        new_body = _replace_section(existing_body, section, content)
        status, _ = _api(
            "PATCH",
            f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}",
            token,
            {"body": new_body},
        )
        ok = status == 200
        if ok:
            print(f"Seção '{section}' atualizada no comentário MAES (ID: {comment_id})")
        else:
            print(f"Erro ao atualizar comentário: HTTP {status}", file=sys.stderr)
        return ok
    else:
        new_body = _new_comment(section, content)
        status, _ = _api(
            "POST",
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            token,
            {"body": new_body},
        )
        ok = status == 201
        if ok:
            print(f"Comentário MAES criado com seção '{section}'")
        else:
            print(f"Erro ao criar comentário: HTTP {status}", file=sys.stderr)
        return ok


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upsert a section in the unified MAES PR review comment",
        epilog=__doc__,
    )
    parser.add_argument("--pr",           required=True, help="Número do PR")
    parser.add_argument(
        "--section",
        required=True,
        choices=["eval", "checklist", "adr", "context"],
        help="Seção a inserir/atualizar",
    )
    parser.add_argument("--content-file", required=True, help="Arquivo com o conteúdo da seção")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo  = os.environ.get("GITHUB_REPOSITORY")

    if not token:
        print("GH_TOKEN ou GITHUB_TOKEN não definido — pulando comentário", file=sys.stderr)
        sys.exit(0)
    if not repo:
        print("GITHUB_REPOSITORY não definido — pulando comentário", file=sys.stderr)
        sys.exit(0)

    try:
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {args.content_file}", file=sys.stderr)
        sys.exit(2)

    ok = upsert_pr_comment(args.pr, args.section, content, repo, token)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
