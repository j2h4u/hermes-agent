"""The image's non-root runtime uses its staged tools and generated assets."""
from __future__ import annotations

import subprocess


def test_python_uses_pm_interpreter_as_runtime_user(built_image: str) -> None:
    probe = """
from pathlib import Path
import json
import os
import sys
import tempfile
from pm.lock import Facts
from pm.install import sealed
from pm.paths import writable_store_root
from pm.registry import get_package
from pm.store import current_target
from pm.workspace import _copy_core_inputs

store = Path(os.environ['HERMES_RUNTIME_DIR'])
stamp = json.loads(Path('/opt/hermes/install-stamp.json').read_text())
manifest = json.loads(Path('/opt/hermes/manifest.json').read_text())
assert (Path('/opt/hermes') / stamp['runtimeDir']).resolve() == store.resolve()
assert (Path('/opt/hermes') / manifest['store']).resolve() == store.resolve()
assert (Path('/opt/hermes') / manifest['runtime']['toolsDir']).resolve() == store.resolve()
assert sealed() and writable_store_root() != store
with tempfile.TemporaryDirectory() as directory:
    _copy_core_inputs(Path('/opt/hermes'), Path(directory))
    assert not (Path(directory) / store.relative_to('/opt/hermes')).exists(), 'the tool store entered a plugin source snapshot'
assert not list(store.glob('fetch-*')), 'completed download archives must not ship'
fact = Facts(store / 'facts.json').get('python')
expected = get_package('python').binary(store / fact['entry'], current_target())
assert Path(sys._base_executable).resolve() == expected.resolve()
import hermes_yaml as yaml
print('PM interpreter and application dependencies load as hermes')
"""
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", "hermes",
         "--entrypoint", "/opt/hermes/.venv/bin/python", built_image, "-c", probe],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_ships_generated_icon_without_build_environment(built_image: str) -> None:
    probe = """
from pathlib import Path
from PIL import Image

with Image.open('/opt/hermes/hermes_cli/web_dist/favicon.ico') as image:
    image.load()
    assert image.width > 0 and image.height > 0
assert not Path('/opt/hermes/node_modules/vite').exists()
assert not Path('/opt/hermes/node_modules/esbuild').exists()
assert Path('/opt/hermes/node_modules/typescript/bin/tsc').is_file()
"""
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", "hermes",
         "--entrypoint", "/opt/hermes/.venv/bin/python", built_image, "-c", probe],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
