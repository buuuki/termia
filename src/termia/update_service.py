# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Release policy and bounded official downloads. No GTK or installation code."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from threading import Event
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = "https://github.com/buuuki/termia"
API = "https://api.github.com/repos/buuuki/termia"
MAX_PACKAGE = 100 * 1024 * 1024


class UpdateError(Exception):
    """A translation key, never raw network/process output."""


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise UpdateError("update_cancelled")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    stage: int
    serial: int
    released: int

    @classmethod
    def parse(cls, value: str) -> Version:
        match = re.fullmatch(
            r"v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(?:\.(\d+))?)?(-dev)?", value
        )
        if not match:
            raise ValueError("Unsupported version")
        major, minor, patch, stage, serial, dev = match.groups()
        return cls(int(major), int(minor), int(patch),
                   {"alpha": 0, "beta": 1, "rc": 2, None: 3}[stage],
                   int(serial or 1), int(not dev))


@dataclass(frozen=True)
class Asset:
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Release:
    tag: str
    version: Version
    asset: Asset | None

    @property
    def url(self) -> str:
        return f"{REPOSITORY}/releases/tag/{self.tag}"

    @property
    def label(self) -> str:
        return self.tag.removeprefix("v")


def select_release(items: list[dict], current: str) -> Release | None:
    installed = Version.parse(current)
    candidates = []
    for item in items:
        tag = item.get("tag_name", "")
        if not isinstance(tag, str) or not tag.startswith("v") or item.get("draft"):
            continue
        try:
            version = Version.parse(tag)
        except ValueError:
            continue
        if not version.released or version <= installed:
            continue
        # Prereleases stay in their application line; stable users see stable only.
        if installed.stage < 3:
            if (version.major, version.minor, version.patch) != (
                installed.major, installed.minor, installed.patch
            ):
                continue
        elif version.stage < 3 or item.get("prerelease"):
            continue
        assets = []
        for raw in item.get("assets", []):
            name, digest = raw.get("name", ""), raw.get("digest", "") or ""
            url, size = raw.get("browser_download_url", ""), raw.get("size", 0)
            if (isinstance(name, str) and re.fullmatch(r"termia_[A-Za-z0-9.~+\-]+_all\.deb", name)
                    and url == f"{REPOSITORY}/releases/download/{tag}/{name}"
                    and isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                    and type(size) is int and 0 < size <= MAX_PACKAGE):
                assets.append(Asset(url, digest[7:], size))
        candidates.append(Release(tag, version, assets[0] if len(assets) == 1 else None))
    return max(candidates, key=lambda release: release.version, default=None)


def allowed_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    if parsed.hostname == "api.github.com":
        return parsed.path.startswith("/repos/buuuki/termia/releases")
    if parsed.hostname == "github.com":
        return parsed.path.startswith("/buuuki/termia/releases/download/")
    return parsed.hostname == "release-assets.githubusercontent.com"


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise UpdateError("update_untrusted")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ReleaseClient:
    def __init__(self, opener=None):
        self.opener = opener or build_opener(OfficialRedirects())

    def read(self, url: str, cancel: Event, limit: int, output=None) -> bytes:
        if not allowed_url(url):
            raise UpdateError("update_untrusted")
        check_cancel(cancel)
        request = Request(url, headers={"User-Agent": "Termia-Updater",
                                       "Accept": "application/vnd.github+json" if url.startswith(API) else "application/octet-stream"})
        deadline = time.monotonic() + 120
        try:
            with self.opener.open(request, timeout=10) as response:
                chunks, count = [], 0
                while True:
                    check_cancel(cancel)
                    if time.monotonic() > deadline:
                        raise UpdateError("update_network_failed")
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > limit:
                        raise UpdateError("update_untrusted")
                    if output is None:
                        chunks.append(block)
                    else:
                        output.write(block)
                check_cancel(cancel)
                return b"".join(chunks)
        except UpdateError:
            raise
        except Exception:
            raise UpdateError("update_network_failed") from None

    def releases(self, cancel: Event) -> list[dict]:
        result = []
        for page in range(1, 11):
            try:
                items = json.loads(self.read(f"{API}/releases?per_page=100&page={page}", cancel, 4 * 1024 * 1024))
                if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                    raise ValueError()
            except (ValueError, TypeError):
                raise UpdateError("update_untrusted") from None
            result.extend(items)
            if len(items) < 100:
                return result
        raise UpdateError("update_network_failed")

    def download(self, asset: Asset, destination: Path, cancel: Event) -> None:
        created = False
        try:
            with destination.open("xb") as output:
                created = True
                self.read(asset.url, cancel, asset.size, output)
            check_cancel(cancel)
            digest = hashlib.sha256()
            with destination.open("rb") as source:
                for block in iter(lambda: source.read(64 * 1024), b""):
                    digest.update(block)
            if destination.stat().st_size != asset.size or digest.hexdigest() != asset.sha256:
                raise UpdateError("update_untrusted")
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
