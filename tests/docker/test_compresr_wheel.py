"""Patched Compresr artifacts keep their content hash across image rebuilds."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import os
import time
import unittest
import zipfile
from importlib.metadata import PathDistribution
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class CompresrWheelTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory(prefix="compresr-wheel-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = Path(__file__).resolve().parents[2] / "docker" / "patch_compresr_threshold.py"
        spec = importlib.util.spec_from_file_location("compresr_wheel_patch", source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.__file__ = str(self.root / "docker" / source.name)
        Path(self.module.__file__).parent.mkdir()
        self.package_root = self.root / "site-packages"
        self.record_name = f"compresr-{self.module.TARGET_VERSION}.dist-info/RECORD"
        metadata = self.record_name.rsplit("/", 1)[0]
        self.contents = {
            "compresr/integrations/hermes/engine.py": b"threshold_tokens_cap = 120000\n",
            "compresr/__init__.py": b"",
            f"{metadata}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
            f"{metadata}/METADATA": (
                f"Name: compresr\nVersion: {self.module.TARGET_VERSION}\n".encode()
            ),
        }
        for name, data in self.contents.items():
            path = self.package_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.record = self.package_root / self.record_name
        self.entries = [
            *self.contents,
            self.record_name,
            f"{metadata}/INSTALLER",
            f"{metadata}/REQUESTED",
            "compresr/__pycache__/__init__.pyc",
            "../../../bin/compresr",
        ]
        self._write_record(self.entries)
        self.package = PathDistribution(self.record.parent)

    def _write_record(self, entries: list[str]) -> None:
        with self.record.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows((name, "", "") for name in entries)

    def test_identical_bytes_despite_clock_file_metadata_and_record_order(self) -> None:
        first_clock = time.struct_time((2020, 1, 2, 3, 4, 6, 3, 2, -1))
        second_clock = time.struct_time((2030, 6, 7, 8, 9, 10, 4, 158, -1))
        with patch("zipfile.time.localtime", return_value=first_clock):
            self.module.write_patched_wheel(self.package)
        output = next((self.root / "docker").rglob("*.whl"))
        original = output.read_bytes()
        self._write_record(list(reversed(self.entries)))
        for name in self.contents:
            path = self.package_root / name
            path.chmod(0o600)
            os.utime(path, (1_900_000_000, 1_900_000_000))
        with patch("zipfile.time.localtime", return_value=second_clock):
            self.module.write_patched_wheel(self.package)
        self.assertEqual(original, output.read_bytes())

    def test_wheel_records_every_payload_hash_and_stable_metadata(self) -> None:
        self.module.write_patched_wheel(self.package)
        output = self.root / "docker" / "compresr-patched" / (
            f"compresr-{self.module.TARGET_VERSION}-py3-none-any.whl"
        )
        with zipfile.ZipFile(output) as wheel:
            self.assertEqual(wheel.namelist(), [*sorted(self.contents), self.record_name])
            rows = list(csv.reader(io.StringIO(wheel.read(self.record_name).decode())))
            self.assertEqual([row[0] for row in rows], wheel.namelist())
            self.assertEqual(rows[-1], [self.record_name, "", ""])
            for name, digest, size in rows[:-1]:
                payload = wheel.read(name)
                self.assertEqual(payload, self.contents[name])
                expected = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
                self.assertEqual(digest, f"sha256={expected.decode()}")
                self.assertEqual(size, str(len(payload)))
            for entry in wheel.infolist():
                self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(entry.create_system, 3)
                self.assertEqual(entry.external_attr >> 16, 0o100644)
                self.assertEqual(entry.compress_type, zipfile.ZIP_DEFLATED)
