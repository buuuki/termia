"""Validate downloaded release assets before approving publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from threading import Event

from termia import __version__
from termia.update_installers import command
from termia.update_service import REPOSITORY, UpdateError


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(release: dict, directory: Path, approved_sha: str,
             readmes: list[Path], *, published: bool = False) -> None:
    tag = "v" + __version__
    require(release["tag_name"] == tag, "Release tag differs from source version")
    require(release["draft"] is (not published), "Unexpected draft/published state")
    require(release["prerelease"] is ("-" in __version__), "Incorrect prerelease state")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", approved_sha)), "Invalid approved SHA-256")
    assets = release["assets"]
    packages = [asset for asset in assets if asset["name"].endswith(".deb")]
    require(len(packages) == 1 and len(assets) == 2, "Expected one package and SHA256SUMS")
    asset = packages[0]
    name = asset["name"]
    require(bool(re.fullmatch(r"termia_[0-9A-Za-z.+_-]+_all\.deb", name)),
            "Unsafe or noncanonical public filename")
    require({item["name"] for item in assets} == {name, "SHA256SUMS"}, "Unexpected assets")
    for item in assets:
        expected_url = f"{REPOSITORY}/releases/download/{tag}/{item['name']}"
        require(item["browser_download_url"] == expected_url, "Asset URL/name mismatch")
        path = directory / item["name"]
        require(path.is_file() and not path.is_symlink(), "Missing or symlinked asset")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(item["state"] == "uploaded" and item["size"] == path.stat().st_size,
                "Incomplete asset or size mismatch")
        require(item["digest"] == "sha256:" + digest, "GitHub/download digest mismatch")
    package = directory / name
    require(hashlib.sha256(package.read_bytes()).hexdigest() == approved_sha,
            "Package differs from approved bytes")
    require((directory / "SHA256SUMS").read_text() == f"{approved_sha}  {name}\n",
            "Checksum file does not match the public filename and approved bytes")
    fields = [command(["/usr/bin/dpkg-deb", "--field", str(package.resolve()), field], Event())
              for field in ("Package", "Version", "Architecture")]
    version = fields[1]
    require(fields[0] == "termia" and fields[2] == "all", "Wrong package or architecture")
    require(bool(re.fullmatch(re.escape(__version__.replace("-", "~", 1)) + r"-[1-9][0-9]*",
                              version)), "Internal Debian version differs from source")
    require(name == f"termia_{version.replace('~', '.')}_all.deb",
            "Public filename differs from internal Debian version")
    url = asset["browser_download_url"]
    require(f"sudo apt install ./{name}" in release["body"], "Release install command mismatch")
    require(f"\x60{name}\x60" in release["body"], "Release download filename mismatch")
    for readme in readmes:
        text = readme.read_text()
        urls = re.findall(r"https://github\.com/buuuki/termia/releases/download/[^\s)]+", text)
        require(urls == [url], f"Download URL mismatch: {readme}")
        require(f"sudo apt install ./{name}" in text, f"Install command mismatch: {readme}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--published", action="store_true")
    args = parser.parse_args()
    try:
        validate(json.loads(args.release_json.read_text()), args.assets, args.sha256,
                 [Path(name) for name in ("README.md", "docs/README.es.md", "docs/README.ca.md")],
                 published=args.published)
    except (OSError, ValueError, KeyError, TypeError, UpdateError) as error:
        parser.exit(1, f"Release validation failed: {error}\n")
    print("Release filenames, approved bytes, versions, notes and README links agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
