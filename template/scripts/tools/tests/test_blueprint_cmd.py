"""Tests for maes.blueprint_cmd — o catálogo determinístico de Blueprints.

Cobre list/show/prompt/bootstrap/seed/validate (incl. execução sem projeto) e o
invariante do Blueprint Selection Principle (não-inferência): nenhum blueprint.yaml
carrega campos de matching e o agente /maes-create exige escolha explícita.
"""

import yaml

import maes.blueprint_cmd as bc
import maes.compiler as compiler
import maes.init_cmd as ic

# Campos proibidos no contrato — matching/inferência de stack (Blueprint Selection Principle).
_FORBIDDEN_MANIFEST_FIELDS = ("match", "keywords", "intent", "recommendation")


# ─── list / show / prompt / bootstrap (sem projeto) ──────────────────────────────

def test_list_shows_all_blueprints(capsys):
    rc = bc.cmd_list()
    out = capsys.readouterr().out
    assert rc == 0
    # Todos os blueprints empacotados aparecem no catálogo (inclui os novos).
    for bp_id in ("nestjs-api", "react-spa", "nextjs-web", "fastapi-api"):
        assert bp_id in out, f"{bp_id} não apareceu em `blueprint list`"


def test_show_known_blueprint(capsys):
    rc = bc.cmd_show("nestjs-api")
    out = capsys.readouterr().out
    assert rc == 0
    assert "NestJS API Corporativa" in out
    assert "backend-api" in out


def test_show_unknown_blueprint_exits_1(capsys):
    rc = bc.cmd_show("does-not-exist")
    out = capsys.readouterr().out
    assert rc == 1
    assert "não encontrado" in out


def test_prompt_emits_operational_context(capsys):
    rc = bc.cmd_prompt("react-spa")
    out = capsys.readouterr().out
    assert rc == 0
    assert "React SPA Corporativo" in out


def test_prompt_unknown_exits_1():
    assert bc.cmd_prompt("nope") == 1


def test_bootstrap_emits_recipe(capsys):
    rc = bc.cmd_bootstrap("nestjs-api")
    out = capsys.readouterr().out
    assert rc == 0
    assert "steps:" in out
    assert "strategy:" in out


def test_bootstrap_unknown_exits_1():
    assert bc.cmd_bootstrap("nope") == 1


# ─── seed (exige projeto) ────────────────────────────────────────────────────────

def test_seed_populates_human_context(tmp_path, capsys):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)

    rc = bc.cmd_seed("nestjs-api", maes_dir)
    capsys.readouterr()
    assert rc == 0

    human = maes_dir / "context" / "human"
    assert (human / "principles.md").exists()
    assert (human / "decisions.md").exists()
    # Nunca toca synthesis/ nem inferred/.
    assert not (maes_dir / "synthesis").exists()
    assert not (maes_dir / "context" / "inferred").exists()


def test_seed_is_idempotent(tmp_path):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0  # segunda vez não falha


def test_seed_unknown_exits_1(tmp_path):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    assert bc.cmd_seed("nope", maes_dir) == 1


# ─── proveniência (escrita determinística pelo CLI — ADR 0003/0006) ──────────────

def _make_project(tmp_path):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    (maes_dir / "config.yaml").write_text(
        "meta:\n  maes_version: \"1.1.0\"\n\nproject:\n  name: \"demo\"\n",
        encoding="utf-8",
    )
    return maes_dir


def test_seed_writes_provenance_to_config(tmp_path):
    maes_dir = _make_project(tmp_path)
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0

    config = yaml.safe_load((maes_dir / "config.yaml").read_text(encoding="utf-8"))
    bp = config["blueprint"]
    assert bp["id"] == "nestjs-api"
    assert bp["version"]                       # versão do contrato registrada
    assert "created_at" in bp
    # Distinto de meta.maes_version — e este permanece intacto.
    assert config["meta"]["maes_version"] == "1.1.0"
    assert "source_hash" not in bp             # decisão futura (RFC 0001 §10)
    assert "organization" not in bp            # decisão futura


def test_seed_provenance_is_idempotent(tmp_path):
    maes_dir = _make_project(tmp_path)
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0
    first = (maes_dir / "config.yaml").read_text(encoding="utf-8")
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0
    second = (maes_dir / "config.yaml").read_text(encoding="utf-8")
    assert first == second                     # não duplica nem reescreve o bloco
    assert second.count("\nblueprint:") == 1


def test_seed_without_config_does_not_create_one(tmp_path):
    # Sem projeto config.yaml, o seed copia o contexto mas não fabrica config.
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    assert bc.cmd_seed("nestjs-api", maes_dir) == 0
    assert not (maes_dir / "config.yaml").exists()


# ─── validate ────────────────────────────────────────────────────────────────────

def test_validate_all_packaged_blueprints_ok(capsys):
    rc = bc.cmd_validate()
    out = capsys.readouterr().out
    assert rc == 0
    assert "nestjs-api" in out and "react-spa" in out
    assert "íntegro" in out


def test_validate_rejects_broken_blueprint(tmp_path, monkeypatch, capsys):
    # Catálogo temporário com um Blueprint faltando prompt.md / bootstrap / human.
    catalog = tmp_path / "blueprints"
    broken = catalog / "broken"
    broken.mkdir(parents=True)
    (broken / "blueprint.yaml").write_text(
        # falta 'type' e 'summary'; seed_human=true sem context/human
        "id: broken\nname: Broken\nversion: 1.0.0\nseed_human: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bc, "_BLUEPRINTS_DIR", catalog)

    rc = bc.cmd_validate("broken")
    out = capsys.readouterr().out
    assert rc == 1
    assert "prompt.md ausente" in out
    assert "bootstrap/bootstrap.yaml ausente" in out
    assert "context/human/ ausente" in out


# ─── conteúdo arquitetural: Intended Placement → guards (RFC 0001 §9) ────────────

_PLACEMENT_ROOT = {"nestjs-api": "src/modules", "react-spa": "src/features"}


def test_boundaries_become_enforcement_guards_requires_approval():
    """boundaries.md (layer 4) com regra path-bearing vira guard de enforcement
    no tier requires-approval — Intended Placement compilável."""
    for bp_id, root in _PLACEMENT_ROOT.items():
        boundaries = bc._blueprint_dir(bp_id) / "context" / "human" / "boundaries.md"
        assert boundaries.exists(), f"{bp_id} deve semear boundaries.md"
        assertions = compiler._human_assertions_from_file(boundaries, "2026-07-13")
        guards = compiler.derive_guards(assertions)
        enforcement = [g for g in guards if g["guard_type"] == "enforcement"]
        assert enforcement, f"{bp_id}/boundaries.md deveria gerar guards de enforcement"
        assert any(
            g["policy"] == "requires-approval" and any(root in p for p in g["paths"])
            for g in enforcement
        ), f"{bp_id}: esperado guard requires-approval com path sob {root}"


def test_nextjs_web_placement_and_ui_guards():
    """nextjs-web: boundaries (layer 4) gera guard requires-approval sob
    `src/features`; ui-forms-i18n (layer 6) gera guard requires-checklist. Sem
    paths amplos espúrios."""
    bd = bc._blueprint_dir("nextjs-web") / "context" / "human"

    bguards = compiler.derive_guards(
        compiler._human_assertions_from_file(bd / "boundaries.md", "2026-07-13")
    )
    enf = [g for g in bguards if g["guard_type"] == "enforcement"]
    assert any(
        g["policy"] == "requires-approval" and any("src/features" in p for p in g["paths"])
        for g in enf
    )
    # nenhum path amplo (0 subníveis) — higiene A3.
    assert not [p for g in enf for p in g["paths"] if p.strip("/").count("/") == 0]

    uguards = compiler.derive_guards(
        compiler._human_assertions_from_file(bd / "ui-forms-i18n.md", "2026-07-13")
    )
    assert any(
        g["guard_type"] == "enforcement" and g["policy"] == "requires-checklist"
        for g in uguards
    )


def test_fastapi_api_placement_guards():
    """fastapi-api: boundaries (layer 4) gera guards requires-approval de placement
    por camada (app/api, app/services, app/db/models); auth-security (layer 2) gera
    guard block. Sem paths amplos espúrios em nenhum doc."""
    bd = bc._blueprint_dir("fastapi-api") / "context" / "human"

    bguards = compiler.derive_guards(
        compiler._human_assertions_from_file(bd / "boundaries.md", "2026-07-13")
    )
    enf = [g for g in bguards if g["guard_type"] == "enforcement"]
    assert enf, "boundaries.md deveria gerar guards de enforcement"
    assert all(g["policy"] == "requires-approval" for g in enf)  # layer 4
    assert any(any("app/services" in p for p in g["paths"]) for g in enf)

    # auth-security (layer 2) → tier block quando há path; senão contextual.
    aguards = compiler.derive_guards(
        compiler._human_assertions_from_file(bd / "auth-security.md", "2026-07-13")
    )
    assert aguards, "auth-security.md deveria gerar guards (contextuais/enforcement)"

    # higiene A3: nenhum path amplo (0 subníveis) em qualquer documento.
    import os
    for f in os.listdir(bd):
        if not f.endswith(".md"):
            continue
        for g in compiler.derive_guards(
            compiler._human_assertions_from_file(bd / f, "2026-07-13")
        ):
            broad = [p for p in g["paths"] if g["guard_type"] == "enforcement"
                     and p.strip("/").count("/") == 0]
            assert not broad, f"{f}: path amplo {broad}"


def test_conventions_become_checklist_tier_guards():
    """conventions.md (layer 6) path-bearing vira guard de enforcement no tier
    requires-checklist — a layer escolhida pelo autor define a força (ADR 0007)."""
    for bp_id in _PLACEMENT_ROOT:
        conv = bc._blueprint_dir(bp_id) / "context" / "human" / "conventions.md"
        assert conv.exists(), f"{bp_id} deve semear conventions.md"
        assertions = compiler._human_assertions_from_file(conv, "2026-07-13")
        guards = compiler.derive_guards(assertions)
        assert any(
            g["guard_type"] == "enforcement" and g["policy"] == "requires-checklist"
            for g in guards
        ), f"{bp_id}/conventions.md deveria gerar guard requires-checklist"


# ─── Blueprint Selection Principle — não-inferência ─────────────────────────────

def test_no_manifest_declares_matching_fields():
    """Nenhum blueprint.yaml pode carregar match/keywords/intent/recommendation —
    a escolha é sempre explícita pelo usuário (Blueprint Selection Principle)."""
    for bp_dir in bc._BLUEPRINTS_DIR.iterdir():
        manifest_path = bp_dir / "blueprint.yaml"
        if not manifest_path.exists():
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for field in _FORBIDDEN_MANIFEST_FIELDS:
            assert field not in manifest, (
                f"{bp_dir.name}/blueprint.yaml não pode ter '{field}' "
                f"(viola o Blueprint Selection Principle)"
            )


def test_maes_create_agent_requires_explicit_choice():
    """O agente /maes-create não faz matching e re-apresenta em escolha inválida."""
    agent_path = ic._TEMPLATES_DIR / "agents" / "maes-create.agent.yaml"
    assert agent_path.exists()
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    # Sem campos de matching no contrato do agente.
    for field in _FORBIDDEN_MANIFEST_FIELDS:
        assert field not in agent

    text = (agent.get("persona", "") + agent.get("workflow", {}).get("content", "")).lower()
    assert "escolha explícita" in text or "escolhe explicitamente" in text
    assert "re-apresente" in text or "re-apresentar" in text or "reapresent" in text
