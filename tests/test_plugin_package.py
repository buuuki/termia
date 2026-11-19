import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1]
          / "tools/addon-lab/termia-plugins/package_plugin.py")
spec = importlib.util.spec_from_file_location("plugin_package_test", SOURCE)
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PluginPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="termia-plugin-package-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshot = self.root / "source.tar"
        self.output = self.root / "output"
        self.manifest = {"id": "sample", "version": "0.1.0.dev0", "api_version": 2,
                         "module": "sample_module"}
        self.files = {
            "LICENSE": b"Synthetic license",
            "sample/plugin.json": json.dumps(self.manifest).encode(),
            "sample/src/sample_module/__init__.py": b'raise RuntimeError("must not execute")\n',
            "sample/src/sample_module/locales/en.json": b'{"title": "Sample"}',
            "sample/tests/test_private.py": b"excluded test fixture",
            "another/plugin.json": b"excluded plugin",
        }

    def archive(self, *, mtime=0, link=None):
        with tarfile.open(self.snapshot, "w") as archive:
            for name, data in self.files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mtime = mtime
                archive.addfile(member, io.BytesIO(data))
            if link:
                member = tarfile.TarInfo(link)
                member.type = tarfile.SYMTYPE
                member.linkname = "/synthetic-outside"
                archive.addfile(member)

    def build(self):
        return packaging.build_package(self.snapshot, "sample", self.output)

    def test_bundle_is_complete_scoped_and_has_valid_checksum(self):
        self.archive()
        package, checksum = self.build()
        with tarfile.open(package) as archive:
            self.assertEqual(set(archive.getnames()), {
                "sample/LICENSE", "sample/plugin.json",
                "sample/src/sample_module/__init__.py",
                "sample/src/sample_module/locales/en.json",
            })
            self.assertTrue(all(member.isfile() for member in archive))
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        self.assertEqual(checksum.read_text(), f"{digest}  {package.name}\n")

    def test_output_is_reproducible_despite_source_timestamps(self):
        self.archive(mtime=1)
        first, _ = self.build()
        self.archive(mtime=99999)
        second, _ = packaging.build_package(self.snapshot, "sample", self.root / "second")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_existing_outputs_are_preserved(self):
        self.archive()
        package, _ = self.build()
        original = package.read_bytes()
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(package.read_bytes(), original)

    def test_rejects_links_and_traversal_without_writing_package(self):
        for link in ("sample/src/sample_module/link", "sample/../escape"):
            with self.subTest(link=link):
                self.archive(link=link)
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse(self.output.exists())

    def test_missing_license_or_entry_point_rejected(self):
        for name in ("LICENSE", "sample/src/sample_module/__init__.py"):
            with self.subTest(name=name):
                data = self.files.pop(name)
                self.archive()
                with self.assertRaises(ValueError):
                    self.build()
                self.files[name] = data

    def test_unsafe_manifest_version_rejected(self):
        self.manifest["version"] = "../../escape"
        self.files["sample/plugin.json"] = json.dumps(self.manifest).encode()
        self.archive()
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
