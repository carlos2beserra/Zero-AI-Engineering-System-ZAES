"""Tests for `maes serve --write-mcp-config` target routing.

Regression: Claude Code reads project MCP servers from `.mcp.json` at the
project root, NOT from `.claude/settings.json`. Writing to the latter left the
server silently uninitialized.
"""

import json

import yaml

from maes.__main__ import (
    _ALL_TARGETS,
    _mcp_settings_path,
    _mcp_server_key,
    _write_mcp_config,
)
from maes.init_cmd import _GITIGNORE_ENTRIES, _patch_gitignore


def _maes_dir(tmp_path):
    d = tmp_path / "myproject" / ".maes"
    d.mkdir(parents=True)
    return d


def test_claude_code_target_resolves_to_project_mcp_json(tmp_path):
    project = tmp_path / "myproject"
    assert _mcp_settings_path("claude-code", project) == project / ".mcp.json"


def test_vscode_target_unchanged(tmp_path):
    project = tmp_path / "myproject"
    assert _mcp_settings_path("vscode", project) == project / ".vscode" / "mcp.json"


def test_write_claude_code_writes_mcp_json_and_preapproves(tmp_path):
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent
    server_key = _mcp_server_key(maes_dir)  # maes-myproject

    rc = _write_mcp_config(maes_dir, "claude-code")
    assert rc == 0

    # 1) server definition lands in .mcp.json under mcpServers (where Claude Code reads it)
    mcp_json = project / ".mcp.json"
    assert mcp_json.exists(), ".mcp.json must be created at project root"
    cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
    assert server_key in cfg["mcpServers"]
    # Portable: bare command + cwd-based serve, no machine-specific absolute paths
    # (so the file is safe to commit and works on any clone/machine).
    assert cfg["mcpServers"][server_key]["command"] == "maes"
    assert cfg["mcpServers"][server_key]["args"] == ["serve"]
    assert "--project-dir" not in cfg["mcpServers"][server_key]["args"]

    # 2) NOT written to .claude/settings.json (the ignored location)
    settings = project / ".claude" / "settings.json"
    if settings.exists():
        assert server_key not in json.loads(settings.read_text(encoding="utf-8")).get("mcpServers", {})

    # 3) pre-approved in settings.local.json so it loads without a manual prompt
    local = project / ".claude" / "settings.local.json"
    assert local.exists()
    assert server_key in json.loads(local.read_text(encoding="utf-8"))["enabledMcpjsonServers"]


def test_write_claude_code_preserves_existing_local_settings(tmp_path):
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent
    local = project / ".claude"
    local.mkdir(parents=True)
    (local / "settings.local.json").write_text(
        json.dumps({"enabledMcpjsonServers": ["other"], "permissions": {"allow": []}}),
        encoding="utf-8",
    )

    _write_mcp_config(maes_dir, "claude-code")

    data = json.loads((local / "settings.local.json").read_text(encoding="utf-8"))
    assert "other" in data["enabledMcpjsonServers"]
    assert _mcp_server_key(maes_dir) in data["enabledMcpjsonServers"]
    assert "permissions" in data  # unrelated keys untouched


def test_default_targets_cover_every_adapter():
    # `--write-mcp-config` (no arg) must provision all MCP-capable clients
    # MAES ships an adapter for.
    assert set(_ALL_TARGETS) == {
        "claude-code", "vscode", "cursor-project", "continue", "windsurf",
    }


def test_settings_paths_per_client(tmp_path):
    p = tmp_path / "proj"
    assert _mcp_settings_path("vscode", p) == p / ".vscode" / "mcp.json"
    assert _mcp_settings_path("copilot", p) == p / ".vscode" / "mcp.json"  # alias
    assert _mcp_settings_path("cursor-project", p) == p / ".cursor" / "mcp.json"
    assert _mcp_settings_path("continue", p) == p / ".continue" / "config.yaml"
    assert _mcp_settings_path("windsurf", p).as_posix().endswith(
        ".codeium/windsurf/mcp_config.json"
    )


def test_write_continue_yaml_list(tmp_path):
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent
    key = _mcp_server_key(maes_dir)

    _write_mcp_config(maes_dir, "continue")

    cfg = yaml.safe_load((project / ".continue" / "config.yaml").read_text(encoding="utf-8"))
    servers = cfg["mcpServers"]
    assert isinstance(servers, list)  # Continue's schema is a list, not a dict
    entry = next(s for s in servers if s["name"] == key)
    assert entry["command"] == "maes"
    assert entry["args"] == ["serve"]  # portable, no absolute --project-dir


def test_write_continue_preserves_existing_config(tmp_path):
    maes_dir = _maes_dir(tmp_path)
    cont = maes_dir.parent / ".continue"
    cont.mkdir(parents=True)
    (cont / "config.yaml").write_text(
        "name: my-config\nmodels:\n  - name: gpt\n"
        "mcpServers:\n  - name: other\n    command: foo\n",
        encoding="utf-8",
    )

    _write_mcp_config(maes_dir, "continue")

    cfg = yaml.safe_load((cont / "config.yaml").read_text(encoding="utf-8"))
    names = [s["name"] for s in cfg["mcpServers"]]
    assert "other" in names and _mcp_server_key(maes_dir) in names
    assert cfg["name"] == "my-config" and cfg["models"]  # unrelated keys untouched


def test_copilot_uses_vscode_servers_key(tmp_path):
    maes_dir = _maes_dir(tmp_path)
    _write_mcp_config(maes_dir, "copilot")
    cfg = json.loads((maes_dir.parent / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    entry = cfg["servers"][_mcp_server_key(maes_dir)]
    assert entry["type"] == "stdio"


def test_write_all_provisions_every_client(tmp_path, monkeypatch):
    # Redirect HOME so the user-global windsurf write lands in tmp, not real home.
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent

    assert _write_mcp_config(maes_dir, "__all__") == 0

    assert (project / ".mcp.json").exists()
    assert (project / ".vscode" / "mcp.json").exists()
    assert (project / ".cursor" / "mcp.json").exists()
    assert (project / ".continue" / "config.yaml").exists()
    assert (home / ".codeium" / "windsurf" / "mcp_config.json").exists()


def test_project_targets_are_portable_no_absolute_paths(tmp_path):
    # No project-scoped config may contain a machine-specific absolute path.
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent
    for target in ("claude-code", "vscode", "cursor-project", "continue"):
        _write_mcp_config(maes_dir, target)
    blobs = [
        (project / ".mcp.json").read_text(encoding="utf-8"),
        (project / ".vscode" / "mcp.json").read_text(encoding="utf-8"),
        (project / ".cursor" / "mcp.json").read_text(encoding="utf-8"),
        (project / ".continue" / "config.yaml").read_text(encoding="utf-8"),
    ]
    for blob in blobs:
        assert str(project) not in blob       # no absolute project path
        assert "--project-dir" not in blob     # cwd-based instead
        assert ":\\" not in blob and ":/" not in blob  # no absolute drive paths


def test_windsurf_global_pins_project_dir(tmp_path, monkeypatch):
    # Global configs have no project cwd, so they MUST keep --project-dir
    # (they live in ~ and are not versioned, so absolute is fine there).
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    maes_dir = _maes_dir(tmp_path)
    project = maes_dir.parent

    _write_mcp_config(maes_dir, "windsurf")

    cfg = json.loads((home / ".codeium" / "windsurf" / "mcp_config.json").read_text(encoding="utf-8"))
    entry = cfg["mcpServers"][_mcp_server_key(maes_dir)]
    assert entry["command"] == "maes"
    assert entry["args"] == ["--project-dir", str(project), "serve"]


def test_gitignore_ignores_local_settings_but_not_mcp_json(tmp_path):
    # The user-private pre-approval file must be git-ignored; the shared
    # .mcp.json must NOT be (it is committed for the whole team).
    assert ".claude/settings.local.json" in _GITIGNORE_ENTRIES
    assert not any(e.strip().rstrip("/") == ".mcp.json" for e in _GITIGNORE_ENTRIES)

    _patch_gitignore(tmp_path)
    gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".claude/settings.local.json" in gi
    assert ".mcp.json" not in gi
