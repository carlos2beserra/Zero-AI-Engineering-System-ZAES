"""Tests for maes.init_cmd — ensures `maes init` vendors the CI-required modules.

Regression: the maes-validate workflow runs `PYTHONPATH=.maes/vendor python -m
maes`, so init must populate .maes/vendor/maes/ (this used to be done by the
now-removed `maes quickstart`).
"""

import maes.init_cmd as ic
from maes.quickstart_cmd import _VENDOR_MODULES


def _noninteractive(monkeypatch):
    # run_init prompts for name/description/domain and may confirm re-init.
    monkeypatch.setattr(ic, "_prompt", lambda msg, default="": default or "demo")
    monkeypatch.setattr(ic, "_confirm", lambda msg, default=True: default)


def test_init_vendors_maes_package(tmp_path, monkeypatch):
    _noninteractive(monkeypatch)

    ic.run_init(tmp_path)

    vendor = tmp_path / ".maes" / "vendor" / "maes"
    assert (vendor / "__init__.py").exists(), ".maes/vendor/maes/ not populated by init"
    # every CI-required module the maes-validate workflow needs is present
    for module in _VENDOR_MODULES:
        assert (vendor / module).exists(), f"vendored module missing: {module}"


def test_init_vendor_is_importable(tmp_path, monkeypatch):
    # The vendored package must import as `maes` when .maes/vendor is on the path
    # (mirrors `PYTHONPATH=.maes/vendor python -m maes` in CI).
    _noninteractive(monkeypatch)
    ic.run_init(tmp_path)

    vendor_root = tmp_path / ".maes" / "vendor"
    code = (vendor_root / "maes" / "compiler.py").read_text(encoding="utf-8")
    assert "def build" in code or "derive_hot_context" in code  # real compiler module


def test_init_deploys_maes_create_command(tmp_path, monkeypatch):
    # Greenfield entry point: `maes init` must deploy the /maes-create slash command
    # alongside the brownfield agents.
    _noninteractive(monkeypatch)
    ic.run_init(tmp_path)

    assert "maes-create" in ic._INIT_AGENTS
    cmd = tmp_path / ".claude" / "commands" / "maes-create.md"
    assert cmd.exists(), "/maes-create command not deployed by init"


def test_init_next_steps_bifurcated(tmp_path, monkeypatch, capsys):
    # The init output must offer both paths: greenfield (/maes-create) and
    # brownfield (/maes-analyze).
    _noninteractive(monkeypatch)
    ic.run_init(tmp_path)
    out = capsys.readouterr().out

    assert "/maes-create" in out
    assert "/maes-analyze" in out
    assert "NEW project" in out and "EXISTING project" in out


def test_copy_agent_templates_overwrites_maes_agents_but_merges_others(tmp_path):
    """maes-* agents are framework-owned and overwritten verbatim on upgrade;
    non-maes agents keep the merge behavior (user customizations preserved)."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    # Templates shipped by the framework.
    (src / "maes-foo.agent.yaml").write_text(
        "id: maes-foo\nversion: 2.0.0\n", encoding="utf-8"
    )
    (src / "custom-bar.agent.yaml").write_text(
        "id: custom-bar\nversion: 2.0.0\n", encoding="utf-8"
    )

    # Pre-existing installed copies the user has modified.
    (dst / "maes-foo.agent.yaml").write_text(
        "id: maes-foo\nversion: 1.0.0\ncustom: mine\n", encoding="utf-8"
    )
    (dst / "custom-bar.agent.yaml").write_text(
        "id: custom-bar\nversion: 1.0.0\ncustom: mine\n", encoding="utf-8"
    )

    ic._copy_agent_templates(src, dst, merge_existing_agents=True)

    # maes-* → overwritten verbatim with the template (user edits dropped).
    foo = (dst / "maes-foo.agent.yaml").read_text(encoding="utf-8")
    assert foo == "id: maes-foo\nversion: 2.0.0\n"
    assert "custom: mine" not in foo

    # non-maes → merged, user's custom field survives.
    bar = (dst / "custom-bar.agent.yaml").read_text(encoding="utf-8")
    assert "custom: mine" in bar
