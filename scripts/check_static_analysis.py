"""Compare analyzer findings without checking out or executing project code."""

from __future__ import annotations

import argparse
import ast
import asyncio
import io
import json
import re
import shutil
import tarfile
import tempfile
import tokenize
from collections import Counter
from pathlib import Path


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


def report_difference(tool: str, baseline: list[dict], proposed: list[dict]) -> int:
    remaining = Counter(item["key"] for item in baseline)
    new = 0
    for item in proposed:
        key = item["key"]
        existing = remaining[key] > 0
        if existing:
            remaining[key] -= 1
        else:
            new += 1
        # No code, credential literals, absolute paths or workflow commands.
        print(json.dumps({"tool": tool, "status": "existing" if existing else "new",
                          **{k: v for k, v in item.items() if k != "key"}}, sort_keys=True))
    print(f"{tool}: baseline={len(baseline)} proposed={len(proposed)} new={new}")
    return new


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


async def check(base: str, head: str) -> int:
    repo = Path((await git(Path.cwd(), "rev-parse", "--show-toplevel")).decode().strip()).resolve()
    for tool, version in read_pins(Path(__file__).resolve().parents[1] / "requirements-ci.txt").items():
        status, output = await command([tool, "--version"], repo)
        if status or output.decode().splitlines()[:1] != [f"{tool} {version}"]:
            raise AnalysisError(f"Install the pinned {tool} version from requirements-ci.txt")
    base_sha = (await git(repo, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")).decode().strip()
    head_sha = (await git(repo, "rev-parse", "--verify", "--end-of-options",
                          ("HEAD" if head == "WORKTREE" else head) + "^{commit}")).decode().strip()
    with tempfile.TemporaryDirectory(prefix="termia-analysis-") as temporary:
        roots = [Path(temporary) / name for name in ("base", "head")]
        for root in roots:
            root.mkdir()
        await snapshot(repo, base_sha, roots[0])
        await snapshot(repo, "WORKTREE" if head == "WORKTREE" else head_sha, roots[1])
        new = 0
        for tool in ("ruff", "bandit"):
            before, after = await asyncio.gather(*(analyze(tool, root) for root in roots))
            new += report_difference(tool, before, after)
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
