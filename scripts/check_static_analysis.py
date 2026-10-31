"""Compare analyzer findings without checking out or executing project code."""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import tokenize
from collections import Counter
from pathlib import Path

QUALITY_ADOPTION_COMMIT = "fb584fc2906568cb62cd6f12b0831cd80fec682e"
APPROVED_RELEASE_BASELINE = "50e747d1edaf2610aa6b0fdfc98675a8256493bb"
REVIEW_FILE = ".github/static-analysis-reviews.json"
REVIEW_RULES = {"B404", "B603", "B606"}


class AnalysisError(RuntimeError):
    """Missing evidence or failed tooling must not produce a green check."""


async def command(args: list[str], cwd: Path, *, timeout: float = 300) -> tuple[int, bytes]:
    executable = shutil.which(args[0])
    if executable is None:
        raise AnalysisError(f"Required executable unavailable: {args[0]}")
    process = await asyncio.create_subprocess_exec(
        str(Path(executable).resolve()), *args[1:], cwd=cwd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    return process.returncode, stdout


async def git(repo: Path, *args: str) -> bytes:
    status, output = await command(["git", *args], repo)
    if status:
        raise AnalysisError(f"Git {args[0]} failed; verify refs and fetched history")
    return output


def python_file(name: str) -> bool:
    return name.endswith(".py") and not {".venv", "venv"}.intersection(Path(name).parts)


def destination(root: Path, name: str) -> Path:
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or not path.resolve().is_relative_to(root.resolve()):
        raise AnalysisError("Unsafe source path")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def snapshot(repo: Path, ref: str, root: Path) -> None:
    if ref == "WORKTREE":
        names = (await git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")).decode().split("\0")
        for name in sorted(set(filter(python_file, names))):
            source = repo / name
            if not source.exists() and not source.is_symlink():
                continue  # A local deletion belongs to the proposed tree.
            if source.is_symlink() or not source.resolve().is_relative_to(repo):
                raise AnalysisError("Source symlinks are not supported")
            target = destination(root, name)
            target.write_bytes(source.read_bytes())
            target.chmod(0o700 if source.stat().st_mode & 0o111 else 0o600)
        return
    archive = await git(repo, "archive", "--format=tar", ref)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree:
            if not python_file(member.name):
                continue
            if not member.isfile():
                raise AnalysisError("Source symlinks and special files are not supported")
            source = tree.extractfile(member)
            if source is None:
                raise AnalysisError("Missing archived source")
            target = destination(root, member.name)
            target.write_bytes(source.read())
            target.chmod(0o700 if member.mode & 0o111 else 0o600)
    expected = (await git(repo, "ls-tree", "-r", "--name-only", "-z", ref)).decode().split("\0")
    if {p for p in expected if python_file(p)} != {p.relative_to(root).as_posix() for p in root.rglob("*.py")}:
        raise AnalysisError("Archive omitted tracked Python files; inspect export attributes")


def fingerprint(path: str, rule: str, message: str, severity: str, source: str) -> tuple:
    # Ignore line shifts/indentation, retain literal contents and duplicate counts.
    try:
        tokens = tuple(
            (token.type, token.string) for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type not in {tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE,
                                  tokenize.NL, tokenize.COMMENT, tokenize.ENDMARKER}
        )
    except (tokenize.TokenError, IndentationError):
        tokens = tuple(line.strip() for line in source.splitlines())
    return path, rule, message, severity, tokens


def bandit_dictionary_source(item: dict, source: str) -> str | None:
    """Identify a B105 dictionary entry without unrelated sibling entries."""
    if item["test_id"] != "B105":
        return None
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if key is not None and (
                key.lineno == item["line_number"]
                and key.col_offset == item.get("col_offset")
            ):
                entry = ast.Tuple(elts=[key, value], ctx=ast.Load())
                return ast.dump(entry, include_attributes=False)
    return None


def parse_report(tool: str, status: int, output: bytes, root: Path) -> list[dict]:
    if status not in (0, 1):
        raise AnalysisError(f"{tool} exited with status {status}")
    try:
        report = json.loads(output)
        if tool == "bandit":
            if report["errors"]:
                raise AnalysisError("Bandit could not analyze all files")
            report = report["results"]
        if not isinstance(report, list) or bool(report) != bool(status):
            raise AnalysisError(f"{tool} report disagrees with exit status")
        findings = []
        for item in report:
            path = Path(item["filename"])
            path = path if path.is_absolute() else root / path
            relative = path.resolve().relative_to(root.resolve()).as_posix()
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines()
            if tool == "ruff":
                rule, message, severity = item["code"], item["message"], "unrated"
                if rule == "invalid-syntax":
                    raise AnalysisError("Ruff encountered invalid Python syntax")
                start = item["location"]["row"]
                end = item["end_location"]["row"]
            else:
                rule, message = item["test_id"], item["issue_text"]
                severity = item["issue_severity"] + "/" + item["issue_confidence"]
                start, end = item["line_number"], max(item["line_range"])
            if not isinstance(message, str) or not isinstance(rule, str) or not rule or not 1 <= start <= end <= len(lines):
                raise AnalysisError(f"Invalid {tool} finding location or rule")
            finding_source = "\n".join(lines[start - 1:end])
            if tool == "bandit":
                entry_source = bandit_dictionary_source(item, source)
                if entry_source is not None:
                    finding_source = entry_source
            key = fingerprint(relative, rule, message, severity, finding_source)
            findings.append({"key": key, "file": relative, "line": start, "rule": rule, "severity": severity})
        return findings
    except (ValueError, KeyError, TypeError, OSError, SyntaxError) as exc:
        raise AnalysisError(f"Malformed or incomplete {tool} evidence") from exc


async def analyze(tool: str, root: Path) -> list[dict]:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py"))
    if tool == "bandit":
        files = [name for name in files if not name.startswith("tests/")]
    if not files:
        return []
    flags = (["check", "--isolated", "--target-version", "py310", "--ignore-noqa",
              "--no-cache", "--output-format", "json"] if tool == "ruff"
             else ["--ignore-nosec", "-q", "-f", "json"])
    # Run independent scanners asynchronously, always with argv and no shell.
    status, output = await command([tool, *flags, "--", *files], root)
    return parse_report(tool, status, output, root)


def finding_digest(item: dict) -> str:
    encoded = json.dumps(item["key"], ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def context_digest(path: str, data: bytes) -> str:
    if path.endswith(".py"):
        def normalize(value):
            if isinstance(value, ast.AST):
                fields = [(name, normalize(child)) for name, child in ast.iter_fields(value)
                          if name != "type_params" or child]
                return [type(value).__name__, fields]
            if isinstance(value, list):
                return [normalize(child) for child in value]
            return repr(value)

        tree = normalize(ast.parse(data))
        data = json.dumps(tree, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def review_path(value) -> str:
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value)
            or Path(value).is_absolute() or ".." in Path(value).parts
            or Path(value).as_posix() != value or value == "."):
        raise AnalysisError("Invalid reviewed-source path")
    return value


async def revision_file(repo: Path, ref: str, name: str) -> bytes | None:
    review_path(name)
    if ref == "WORKTREE":
        path = repo / name
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(repo):
            raise AnalysisError("Reviewed files must be regular repository files")
        return path.read_bytes()
    entry = await git(repo, "ls-tree", "-z", ref, "--", name)
    if not entry:
        return None
    metadata, found = entry.rstrip(b"\0").split(b"\t", 1)
    if found.decode() != name or metadata.split()[:2] not in (
            [b"100644", b"blob"], [b"100755", b"blob"]):
        raise AnalysisError("Reviewed files must be regular Git blobs")
    return await git(repo, "show", f"{ref}:{name}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AnalysisError("Duplicate field in static-analysis reviews")
        result[key] = value
    return result


async def load_reviews(repo: Path, ref: str, source: Path, version: str | None,
                       *, required: bool = False) -> dict | None:
    data = await revision_file(repo, ref, REVIEW_FILE)
    if data is None:
        if required:
            raise AnalysisError("Retain the review registry; remove obsolete entries explicitly")
        return None
    try:
        document = json.loads(data, object_pairs_hook=unique_object)
        if (set(document) != {"schema", "bandit_version", "context", "findings"}
                or type(document["schema"]) is not int or document["schema"] != 1
                or not isinstance(document["bandit_version"], str)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", document["bandit_version"])
                or (version is not None and document["bandit_version"] != version)
                or not isinstance(document["context"], dict)
                or not isinstance(document["findings"], list)):
            raise AnalysisError("Invalid static-analysis review registry or analyzer version")
        context = document["context"]
        for name, expected in context.items():
            review_path(name)
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise AnalysisError("Invalid reviewed-context digest")
            content = ((source / name).read_bytes() if name.endswith(".py")
                       else await revision_file(repo, ref, name))
            if content is None or context_digest(name, content) != expected:
                raise AnalysisError("Reviewed context changed; update its documented review")
        reviews, identifiers = {}, set()
        fields = {"id", "file", "rule", "severity", "fingerprint", "reason", "reference"}
        for item in document["findings"]:
            if not isinstance(item, dict) or set(item) != fields:
                raise AnalysisError("Invalid reviewed-finding fields")
            if (not isinstance(item["id"], str) or not re.fullmatch(r"[a-z0-9-]+", item["id"])
                    or item["id"] in identifiers
                    or item["rule"] not in REVIEW_RULES
                    or item["severity"] not in {"LOW/LOW", "LOW/MEDIUM", "LOW/HIGH"}
                    or not isinstance(item["fingerprint"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["fingerprint"])
                    or item["fingerprint"] in reviews
                    or not isinstance(item["reason"], str) or not item["reason"].strip()
                    or not isinstance(item["reference"], str)
                    or not re.fullmatch(r"#[1-9][0-9]*", item["reference"])):
                raise AnalysisError("Invalid or duplicate reviewed finding")
            if review_path(item["file"]) not in context or not item["file"].endswith(".py"):
                raise AnalysisError("Reviewed finding needs its source context")
            identifiers.add(item["id"])
            reviews[item["fingerprint"]] = item
        return reviews
    except (ValueError, TypeError, KeyError, OSError, SyntaxError) as exc:
        raise AnalysisError("Invalid review evidence; recheck registry and source context") from exc


def report_difference(tool: str, baseline: list[dict], proposed: list[dict],
                      reviews: dict | None = None) -> int:
    remaining = Counter(item["key"] for item in baseline)
    new = blocking = reviewed = 0
    seen = set()
    for item in proposed:
        key = item["key"]
        existing = remaining[key] > 0
        if existing:
            remaining[key] -= 1
        else:
            new += 1
        status = "existing" if existing else "new"
        review = reviews.get(finding_digest(item)) if tool == "bandit" and reviews else None
        if review is not None:
            identifier = review["id"]
            if (identifier in seen or any(item[field] != review[field]
                                          for field in ("file", "rule", "severity"))):
                raise AnalysisError("Reviewed finding duplicated or its metadata changed")
            seen.add(identifier)
            reviewed += 1
            status = "reviewed"
        elif not existing:
            blocking += 1
        # No code, credential literals, absolute paths or workflow commands.
        record = {"tool": tool, "status": status,
                  **{k: v for k, v in item.items() if k != "key"}}
        if review is not None:
            record["review_id"] = review["id"]
        print(json.dumps(record, sort_keys=True))
    if reviews is not None and seen != {item["id"] for item in reviews.values()}:
        raise AnalysisError("Stale reviewed finding; remove or renew its documented entry")
    summary = f"{tool}: baseline={len(baseline)} proposed={len(proposed)} new={new}"
    if reviews is not None:
        summary += f" reviewed={reviewed} blocking={blocking}"
    print(summary)
    return blocking


def read_pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(ruff|bandit)==([0-9]+\.[0-9]+\.[0-9]+)", line)
        if match is None or match[1] in pins:
            raise AnalysisError("CI analyzers require unique exact version pins")
        pins[match[1]] = match[2]
    if set(pins) != {"ruff", "bandit"}:
        raise AnalysisError("Both CI analyzers must be pinned")
    return pins


async def is_ancestor(repo: Path, earlier: str, later: str) -> bool:
    status, _output = await command(
        ["git", "merge-base", "--is-ancestor", earlier, later], repo,
    )
    if status not in (0, 1):
        raise AnalysisError("Cannot verify quality-baseline history")
    return status == 0


async def comparison_base(repo: Path, base: str, head: str) -> str:
    if base == head:
        return base
    adoption = (await git(
        repo, "rev-parse", "--verify", "--end-of-options",
        QUALITY_ADOPTION_COMMIT + "^{commit}",
    )).decode().strip()
    if await is_ancestor(repo, adoption, base):
        return base
    approved = (await git(
        repo, "rev-parse", "--verify", "--end-of-options",
        APPROVED_RELEASE_BASELINE + "^{commit}",
    )).decode().strip()
    for earlier, later in ((base, adoption), (adoption, approved), (approved, head)):
        if not await is_ancestor(repo, earlier, later):
            raise AnalysisError("Legacy base requires the approved release lineage")
    print(f"Initial quality adoption: requested_base={base} approved_base={approved}")
    return approved


async def check(base: str, head: str) -> int:
    repo = Path((await git(Path.cwd(), "rev-parse", "--show-toplevel")).decode().strip()).resolve()
    pins = read_pins(Path(__file__).resolve().parents[1] / "requirements-ci.txt")
    for tool, version in pins.items():
        status, output = await command([tool, "--version"], repo)
        if status or output.decode().splitlines()[:1] != [f"{tool} {version}"]:
            raise AnalysisError(f"Install the pinned {tool} version from requirements-ci.txt")
    base_sha = (await git(repo, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")).decode().strip()
    head_sha = (await git(repo, "rev-parse", "--verify", "--end-of-options",
                          ("HEAD" if head == "WORKTREE" else head) + "^{commit}")).decode().strip()
    base_sha = await comparison_base(repo, base_sha, head_sha)
    with tempfile.TemporaryDirectory(prefix="termia-analysis-") as temporary:
        roots = [Path(temporary) / name for name in ("base", "head")]
        for root in roots:
            root.mkdir()
        await snapshot(repo, base_sha, roots[0])
        await snapshot(repo, "WORKTREE" if head == "WORKTREE" else head_sha, roots[1])
        target = "WORKTREE" if head == "WORKTREE" else head_sha
        prior_registry = await revision_file(repo, base_sha, REVIEW_FILE)
        prior_reviews = (await load_reviews(repo, base_sha, roots[0], None)
                         if prior_registry is not None else None)
        reviews = await load_reviews(repo, target, roots[1], pins["bandit"],
                                     required=prior_registry is not None)
        new = 0
        for tool in ("ruff", "bandit"):
            before, after = await asyncio.gather(*(analyze(tool, root) for root in roots))
            if tool == "bandit" and prior_reviews:
                removed = prior_reviews.keys() - (reviews or {}).keys()
                if removed.intersection(finding_digest(item) for item in after):
                    raise AnalysisError("Cannot remove a review while its finding remains")
            new += report_difference(tool, before, after, reviews if tool == "bandit" else None)
        return int(new > 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="PR base ref or previous push SHA; missing refs fail")
    parser.add_argument("--head", default="WORKTREE", help="Commit ref, or WORKTREE including non-ignored new Python files")
    args = parser.parse_args()
    try:
        return asyncio.run(check(args.base, args.head))
    except AnalysisError as exc:
        print(f"Static analysis failed: {exc}")
        return 2
    except (OSError, ValueError, asyncio.TimeoutError, tarfile.TarError) as exc:
        print(f"Static analysis failed: {type(exc).__name__}; check source files, refs and tool pins")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
