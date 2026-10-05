"""A dynamic gateway must finish a >3-second teardown during Docker stop (#130715)."""

import json
import subprocess
from pathlib import Path

from tests.docker.conftest import docker_exec, poll_container, wait_for_container_ready


def test_dynamic_gateway_finishes_before_container_exit(
    built_image: str, container_name: str, tmp_path: Path,
) -> None:
    # No host state, provider keys, or real gateway/SQLite startup is involved.
    # Boot reconciliation creates the actual default slot, with its real permissions.
    try:
        subprocess.run(
            ["docker", "run", "-d", "--name", container_name,
             "--mount", "type=volume,destination=/opt/data,volume-nocopy",
             "-e", "HERMES_UID=10000", "-e", "HERMES_GID=10000",
             built_image, "sleep", "infinity"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        wait_for_container_ready(container_name)
        setup = '''
import pathlib
p = pathlib.Path('/opt/data')
(p / 'gateway_state.json').write_text('{"desired_state":"running"}\\n')
(p / 'shutdown-probe.py').write_text("""
import pathlib, signal, time
p = pathlib.Path('/opt/data/shutdown-receipt')
def stop(signum, frame):
    p.write_text('term\\\\n')
    time.sleep(5)
    p.write_text('closed\\\\n')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
p.write_text('ready\\\\n')
while True:
    signal.pause()
""")
run = pathlib.Path('/run/service/gateway-default/run')
run.write_text('#!/bin/sh\\nexec /opt/hermes/.venv/bin/python /opt/data/shutdown-probe.py\\n')
run.chmod(0o755)
'''
        docker_exec(container_name, "python", "-c", setup).check_returncode()
        docker_exec(
            container_name, "/command/s6-svc", "-u", "/run/service/gateway-default",
        ).check_returncode()
        ready, _ = poll_container(
            container_name, "test \"$(cat /opt/data/shutdown-receipt)\" = ready",
        )
        assert ready, "supervised teardown probe never started"
        subprocess.run(
            ["docker", "stop", "--time", "90", container_name],
            check=True, capture_output=True, text=True, timeout=100,
        )
        for filename in ("shutdown-receipt", "gateway_state.json"):
            subprocess.run(
                ["docker", "cp", f"{container_name}:/opt/data/{filename}", str(tmp_path)],
                check=True, capture_output=True, text=True, timeout=10,
            )
        assert (tmp_path / "shutdown-receipt").read_text(encoding="utf-8") == "closed\n"
        assert json.loads((tmp_path / "gateway_state.json").read_text(encoding="utf-8"))[
            "desired_state"
        ] == "running"
    finally:
        # The image declares /opt/data as a volume; remove this task's anonymous volume too.
        subprocess.run(
            ["docker", "rm", "-f", "-v", container_name],
            check=False, capture_output=True, timeout=30,
        )
