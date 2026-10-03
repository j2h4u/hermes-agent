"""Temporary build-time fix for Compresr 2.9.2 ignoring compression.threshold_tokens.

Remove when the external plugin forwards the cap itself. Unknown package versions
or source changes must fail the build rather than silently lose the limit.
"""

from __future__ import annotations

import hashlib
import base64
import csv
import io
import os
import sys
import zipfile
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

TARGET_VERSION = "2.9.2"
SOURCE_SHA256 = "bc951e104e1bff686e5275f396d497061d89835ccb991c14895fa3673996607a"
CONFIG_SHA256 = "3bf863b548884d1d4393e9ee77a6713202dcdbdeb0d5db744e7de5c921a9f32c"
OLD = '        comp_cfg = read_config_block("compression")\n'
NEW = OLD + '        kwargs.setdefault("threshold_tokens_cap", comp_cfg.get("threshold_tokens"))\n'


def patch_source(source: str, package_version: str) -> str:
    if package_version != TARGET_VERSION:
        raise RuntimeError("Compresr version changed: review/remove the threshold patch")
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Compresr source changed: review/remove the threshold patch")
    if source.count(OLD) != 1:
        raise RuntimeError("Compresr threshold patch anchor is not unique")
    return source.replace(OLD, NEW, 1)


def patch_config_source(source: str) -> str:
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != CONFIG_SHA256:
        raise RuntimeError("Compresr config source changed: review/remove the YAML patch")
    old = "        import yaml\n"
    if source.count(old) != 1:
        raise RuntimeError("Compresr YAML patch anchor is not unique")
    return source.replace(old, "        import hermes_yaml as yaml\n", 1)


def write_patched_wheel(package) -> None:
    """Let PM install the same patched artifact into its dependency generations."""
    output = Path(__file__).with_name(f"compresr-{TARGET_VERSION}-py3-none-any.whl")
    record_path = f"compresr-{TARGET_VERSION}.dist-info/RECORD"
    rows = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as wheel:
        for entry in package.files or ():
            name = str(entry)
            if ".." in entry.parts or name.endswith((".pyc", "/RECORD", "/INSTALLER", "/REQUESTED")):
                continue
            data = Path(package.locate_file(entry)).read_bytes()
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            rows.append((name, f"sha256={digest}", str(len(data))))
            wheel.writestr(name, data)
        record = io.StringIO(newline="")
        csv.writer(record).writerows([*rows, (record_path, "", "")])
        wheel.writestr(record_path, record.getvalue())
    print(f"Built patched wheel: {output.name}")


def verify() -> None:
    """Exercise real config reads and the installed engine, without API calls."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import hermes_bootstrap  # noqa: F401 — exposes the managed Hermes dependencies
    from compresr.integrations.hermes.engine import CompresrContextEngine

    previous_home = os.environ.get("HERMES_HOME")
    with TemporaryDirectory(prefix="compresr-threshold-check-") as home:
        os.environ["HERMES_HOME"] = home
        config = Path(home) / "config.yaml"
        try:
            config.write_text(
                "compression:\n  threshold: 0.5\n  threshold_tokens: 120000\n",
                encoding="utf-8",
            )
            engine = CompresrContextEngine()
            for model, window, expected in (
                ("openai/gpt-6.1-sol", 1_050_000, 120_000),
                ("glm-test", 128_000, 96_000),
                ("small-test", 64_000, 54_400),
                ("openai/gpt-6.1-sol", 1_050_000, 120_000),
            ):
                engine.update_model(model=model, context_length=window)
                assert engine.threshold_tokens_cap == 120_000
                assert engine.threshold_tokens == expected, (model, engine.threshold_tokens)
                assert not engine.should_compress(expected - 1)
                assert engine.should_compress(expected)
                print(f"{model}: window={window}, compression trigger={expected}")
            explicit = CompresrContextEngine(threshold_tokens_cap=90_000)
            explicit.update_model(model="openai/gpt-6.1-sol", context_length=1_050_000)
            assert explicit.threshold_tokens == 90_000
            for value in ("null", "0", "invalid"):
                config.write_text(
                    f"compression:\n  threshold: 0.5\n  threshold_tokens: {value}\n",
                    encoding="utf-8",
                )
                uncapped = CompresrContextEngine()
                uncapped.update_model(model="openai/gpt-6.1-sol", context_length=1_050_000)
                assert uncapped.threshold_tokens_cap is None
                assert uncapped.threshold_tokens == 525_000
            config.write_text("compression:\n  threshold: 0.5\n", encoding="utf-8")
            uncapped = CompresrContextEngine()
            uncapped.update_model(model="openai/gpt-6.1-sol", context_length=1_050_000)
            assert uncapped.threshold_tokens == 525_000
            print("Explicit overrides and absent/invalid caps retain upstream behavior")
        finally:
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify"]:
        verify()
    elif not sys.argv[1:]:
        package = distribution("compresr")
        path = Path(package.locate_file("compresr/integrations/hermes/engine.py"))
        config_path = path.with_name("_config.py")
        patched = patch_source(path.read_text(encoding="utf-8"), package.version)
        patched_config = patch_config_source(config_path.read_text(encoding="utf-8"))
        compile(patched, str(path), "exec")
        compile(patched_config, str(config_path), "exec")
        path.write_text(patched, encoding="utf-8")
        config_path.write_text(patched_config, encoding="utf-8")
        write_patched_wheel(package)
        print("Applied Compresr absolute compression threshold fix")
    else:
        raise SystemExit("usage: patch_compresr_threshold.py [--verify]")
