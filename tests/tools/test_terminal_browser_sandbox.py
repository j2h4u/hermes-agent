"""The default Docker desktop uses Chromium's sandbox without changing other backends."""

from contextlib import nullcontext
import os
import subprocess
from types import SimpleNamespace

import pytest

from hermes_cli.config_defaults import DEFAULT_SANDBOX_IMAGE
from tools.bot_desktop import runtime, sandbox_host
from tools.environments import docker, streams
from tools import browser_session_sandbox


def _docker(image):
    env = object.__new__(docker.DockerEnvironment)
    env._image = image
    return env


def test_arm64_chromium_archive_is_discovered(tmp_path):
    chrome = tmp_path / "chromium-1248" / "chrome-linux-arm64" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("", encoding="utf-8")
    chrome.chmod(0o755)
    result = subprocess.run(["bash", "-c", sandbox_host._CHROMIUM_PROBE],
                            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path)},
                            capture_output=True, text=True, check=True)
    assert result.stdout == str(chrome)


@pytest.mark.parametrize(("image", "expected"), [(DEFAULT_SANDBOX_IMAGE, True), ("custom:desktop", False)])
def test_only_default_docker_image_uses_the_new_browser_policy(image, expected):
    assert sandbox_host.default_docker_browser(_docker(image)) is expected
    assert not sandbox_host.default_docker_browser(SimpleNamespace(_image=image))


def test_ssh_keeps_its_existing_user_policy(monkeypatch):
    from tools.environments.ssh import SSHEnvironment

    env = object.__new__(SSHEnvironment)
    env._image = DEFAULT_SANDBOX_IMAGE
    monkeypatch.setattr(sandbox_host, "_user_for", lambda env: None)
    monkeypatch.setattr(streams, "run_in", lambda *args, **kwargs: pytest.fail("SSH must not gain a UID probe"))
    assert sandbox_host.browser_user(env) is None
    assert not sandbox_host.default_docker_browser(env)


@pytest.mark.parametrize(("uid", "valid"), [(b"1000\n", True), (b"0\n", False), (b"", False)])
def test_default_docker_checks_actual_browser_user(monkeypatch, uid, valid):
    env = _docker(DEFAULT_SANDBOX_IMAGE)
    monkeypatch.setattr(sandbox_host, "_user_for", lambda env: "pn")
    calls = []
    def run_in(env, argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=uid)
    monkeypatch.setattr(streams, "run_in", run_in)
    if valid:
        assert sandbox_host.browser_user(env) == "pn"
    else:
        with pytest.raises(RuntimeError, match="unprivileged"):
            sandbox_host.browser_user(env)
    assert calls[0][1]["user"] == "pn"


@pytest.mark.parametrize(("image", "bypass"), [(DEFAULT_SANDBOX_IMAGE, False), ("custom:desktop", True)])
def test_agent_sandbox_launch_matches_image_policy(monkeypatch, image, bypass):
    env = _docker(image)
    commands = []
    monkeypatch.setattr("tools.browser_session_cloud.chromium_args", list)
    monkeypatch.setattr(streams, "run_in", lambda env, argv, **kwargs: (
        commands.append(argv) or SimpleNamespace(returncode=0, stdout=b"123 456\n", stderr=b"")
    ))
    browser_session_sandbox._start_chromium(env, "pn", "/chrome", "/profile", {})
    assert ("--no-sandbox" in commands[0][2]) is bypass


@pytest.mark.parametrize(("image", "bypass"), [(DEFAULT_SANDBOX_IMAGE, False), ("custom:desktop", True)])
def test_desktop_dock_launch_matches_image_policy(tmp_path, monkeypatch, image, bypass):
    env = _docker(image)
    captured = {}
    monkeypatch.setattr(runtime, "_sandbox_env", lambda create: env)
    monkeypatch.setattr(runtime, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(runtime, "_flocked", lambda path: nullcontext())
    monkeypatch.setattr(runtime, "touch_activity", lambda: None)
    monkeypatch.setattr(runtime, "status", lambda: None)
    monkeypatch.setattr(sandbox_host, "chromium_executable", lambda env: "/chrome")
    monkeypatch.setattr(sandbox_host, "browser_profile_dir", lambda env: "/profile")
    monkeypatch.setattr(sandbox_host, "browser_user", lambda env: "pn")
    monkeypatch.setattr(sandbox_host, "start", lambda env, profile, **kwargs: captured.update(kwargs) or {})
    runtime._start_in_sandbox(1)
    assert ("--no-sandbox" in captured["browser_exec_line"]) is bypass
