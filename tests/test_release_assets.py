import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_release_assets import validate
from termia import __version__
from termia.update_service import REPOSITORY


class ReleaseAssetTests(unittest.TestCase):
    def test_draft_and_published_assets_reject_distribution_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = __version__.replace("-", "~", 1) + "-1"
            name = f"termia_{version.replace('~', '.')}_all.deb"
            data = b"synthetic package bytes"
            sha = hashlib.sha256(data).hexdigest()
            (root / name).write_bytes(data)
            (root / "SHA256SUMS").write_text(f"{sha}  {name}\n")
            release = {"tag_name": "v" + __version__, "draft": True,
                       "prerelease": True, "body": f"\x60{name}\x60\nsudo apt install ./{name}",
                       "assets": []}
            for filename in (name, "SHA256SUMS"):
                path = root / filename
                release["assets"].append({
                    "name": filename, "state": "uploaded", "size": path.stat().st_size,
                    "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                    "browser_download_url":
                        f"{REPOSITORY}/releases/download/v{__version__}/{filename}",
                })
            readme = root / "README.md"
            readme.write_text(release["assets"][0]["browser_download_url"] +
                              f"\nsudo apt install ./{name}")
            with patch("scripts.check_release_assets.command",
                       side_effect=lambda args, _cancel: {
                           "Package": "termia", "Version": version, "Architecture": "all",
                       }[args[-1]]):
                validate(release, root, sha, [readme])
                public = copy.deepcopy(release)
                public["draft"] = False
                validate(public, root, sha, [readme], published=True)
                temporary = copy.deepcopy(release)
                draft_id = "untagged-0123456789abcdef"
                temporary["html_url"] = f"{REPOSITORY}/releases/tag/{draft_id}"
                for item in temporary["assets"]:
                    item["browser_download_url"] = (
                        f"{REPOSITORY}/releases/download/{draft_id}/{item['name']}"
                    )
                validate(temporary, root, sha, [readme])
                for html_url in ("", f"{REPOSITORY}/releases/tag/untagged-9876543210",
                                 f"https://example.invalid/releases/tag/{draft_id}",
                                 f"{REPOSITORY}/releases/tag/{draft_id}?redirect=1"):
                    broken = copy.deepcopy(temporary)
                    broken["html_url"] = html_url
                    with self.subTest(html_url=html_url), self.assertRaises(ValueError):
                        validate(broken, root, sha, [readme])
                for field, value in (
                    ("browser_download_url", f"{REPOSITORY}/releases/download/untagged-ffff/{name}"),
                    ("browser_download_url", f"https://example.invalid/releases/download/{draft_id}/{name}"),
                    ("browser_download_url", temporary["assets"][0]["browser_download_url"] + "?redirect=1"),
                    ("digest", "sha256:" + "0" * 64),
                    ("size", 1),
                ):
                    broken = copy.deepcopy(temporary)
                    broken["assets"][0][field] = value
                    with self.subTest(draft_field=field, value=value), self.assertRaises(ValueError):
                        validate(broken, root, sha, [readme])
                broken = copy.deepcopy(temporary)
                broken["draft"] = False
                with self.assertRaises(ValueError):
                    validate(broken, root, sha, [readme], published=True)
                canonical_readme = readme.read_text()
                readme.write_text(canonical_readme.replace("v" + __version__, draft_id))
                with self.assertRaises(ValueError):
                    validate(temporary, root, sha, [readme])
                readme.write_text(canonical_readme)
                cases = [
                    ("tag_name", "v0.0.0"),
                    ("prerelease", False),
                    ("body", "sudo apt install ./wrong.deb"),
                    ("assets", release["assets"][:1]),
                ]
                for key, value in cases:
                    broken = copy.deepcopy(release)
                    broken[key] = value
                    with self.subTest(key=key), self.assertRaises(ValueError):
                        validate(broken, root, sha, [readme])
                for field, value in (("size", 1), ("digest", "sha256:" + "0" * 64),
                                     ("browser_download_url", "https://example.invalid/package")):
                    broken = copy.deepcopy(release)
                    broken["assets"][0][field] = value
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        validate(broken, root, sha, [readme])
                with self.assertRaises(ValueError):
                    validate(release, root, sha, [readme], published=True)
                with self.assertRaises(ValueError):
                    validate(release, root, "0" * 64, [readme])
                original = (root / "SHA256SUMS").read_bytes()
                (root / "SHA256SUMS").write_text("wrong filename\n")
                with self.assertRaises(ValueError):
                    validate(release, root, sha, [readme])
                (root / "SHA256SUMS").write_bytes(original)
                readme.write_text(readme.read_text().replace(".beta", "~beta"))
                with self.assertRaises(ValueError):
                    validate(release, root, sha, [readme])
