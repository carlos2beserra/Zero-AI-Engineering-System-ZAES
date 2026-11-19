"""Packaging tests — prove the built artifacts actually contain the full MAES
payload and expose the right metadata + console entrypoint.

Regression guard for the distribution phase (Fase 1.5): a wheel that silently
drops template files installs fine but leaves `maes blueprint list` empty. The
per-blueprint ``bootstrap/`` and ``context/`` directories (files without
extensions live there) are the fragile point, so we assert real files — not just
directory presence (empty dirs never make it into a wheel anyway).

Builds both the wheel and the sdist with ``python -m build --no-isolation`` into
a temp dir. Skipped when ``build`` is not installed so the general suite stays
green for contributors who did not install the ``dev`` extra; CI installs
``.[dev,all]`` and therefore always runs it.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

import maes

pytest.importorskip("build", reason="`pip install .[dev]` to run packaging tests")

# tests/ lives at template/scripts/tools/tests/ ; the project (pyproject) is one up.
PROJECT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    """Build wheel + sdist once for the whole module."""
    outdir = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation",
         "--outdir", str(outdir), str(PROJECT_DIR)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"build failed:\n{result.stdout}\n{result.stderr}")
    wheel = next(outdir.glob("maes-*.whl"))
    sdist = next(outdir.glob("maes-*.tar.gz"))
    return wheel, sdist


def _wheel_names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as z:
        return z.namelist()


def _read_dist_info(wheel: Path, suffix: str) -> str:
    with zipfile.ZipFile(wheel) as z:
        name = next(n for n in z.namelist() if n.endswith(f".dist-info/{suffix}"))
        return z.read(name).decode("utf-8")


# Concrete files that MUST ship — code + real template content.
REQUIRED_WHEEL_FILES = [
    "maes/__init__.py",
    "maes/__main__.py",
    "maes/compiler.py",
    "maes/blueprint_cmd.py",
    "maes/templates/agents/maes-analyze.agent.yaml",
    "maes/templates/blueprints/react-spa/blueprint.yaml",
    "maes/templates/blueprints/nestjs-api/blueprint.yaml",
]


def test_wheel_contains_real_files(artifacts):
    wheel, _ = artifacts
    names = set(_wheel_names(wheel))
    missing = [f for f in REQUIRED_WHEEL_FILES if f not in names]
    assert not missing, f"arquivos ausentes no wheel: {missing}"


@pytest.mark.parametrize("blueprint", ["react-spa", "nestjs-api"])
def test_wheel_ships_blueprint_bootstrap_and_context(artifacts, blueprint):
    """bootstrap/ e context/ ficam DENTRO de cada blueprint (não em templates/bootstrap)."""
    wheel, _ = artifacts
    names = _wheel_names(wheel)
    prefix = f"maes/templates/blueprints/{blueprint}"
    assert any(
        n.startswith(f"{prefix}/bootstrap/") and not n.endswith("/") for n in names
    ), f"nenhum arquivo em {prefix}/bootstrap/"
    assert any(
        n.startswith(f"{prefix}/context/") and not n.endswith("/") for n in names
    ), f"nenhum arquivo em {prefix}/context/"


def test_wheel_metadata(artifacts):
    wheel, _ = artifacts
    metadata = _read_dist_info(wheel, "METADATA")
    assert "Name: maes" in metadata
    assert f"Version: {maes.__version__}" in metadata, "versão dinâmica divergente"
    assert "Requires-Python: >=3.9" in metadata


def test_wheel_console_entrypoint(artifacts):
    wheel, _ = artifacts
    entry_points = _read_dist_info(wheel, "entry_points.txt")
    normalized = entry_points.replace(" ", "")
    assert "[console_scripts]" in entry_points
    assert "maes=maes.__main__:main" in normalized, "entrypoint console-script incorreto"


def test_sdist_contains_templates_and_license(artifacts):
    _, sdist = artifacts
    with tarfile.open(sdist) as t:
        names = t.getnames()
    assert any(
        n.endswith("maes/templates/blueprints/react-spa/blueprint.yaml") for n in names
    ), "blueprint ausente no sdist"
    assert any(n.endswith("/LICENSE") or n.endswith("LICENSE") for n in names)


def test_import_and_version():
    assert isinstance(maes.__version__, str) and maes.__version__, "maes.__version__ vazio"
