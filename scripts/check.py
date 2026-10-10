#!/usr/bin/env python3
"""Read-only repository checks. See CONTRIBUTING.md for supported scopes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_DIRS = {
    "docs", "cmd", "internal", "sdk", "web", "protocols", "configs",
    "scripts", "tests", "testdata", ".github",
}
ALLOWED_ROOT_FILES = {
    "README.md", "AGENTS.md", "CONTRIBUTING.md", ".editorconfig",
    ".gitattributes", ".gitignore", "go.mod", "go.sum", "LICENSE",
    "LICENSE.md", "NOTICE", "NOTICE.md",
}
FORBIDDEN_PARTS = {
    ".local", ".worktrees", "build", "dist", "node_modules", "__pycache__",
    ".venv", ".cache", ".idea", ".vscode",
}
ARTIFACT_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo", ".log",
    ".test", ".zip", ".gz", ".tar", ".7z",
}
UNCONFIGURED_SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".js", ".jsx",
    ".ts", ".tsx", ".vue", ".svelte", ".rs", ".java", ".cs",
    ".ps1", ".sh",
}
REQUIRED_FILES = {
    "README.md", "AGENTS.md", "CONTRIBUTING.md", ".editorconfig",
    ".gitattributes", ".gitignore", "scripts/check.py",
    "tests/tooling/test_check.py", "docs/README.md",
    "docs/requirements/README.md", "docs/architecture/README.md",
    "docs/standards/README.md", "docs/standards/layout.md",
    "docs/standards/coding.md", "docs/standards/documentation.md",
    "docs/standards/workflow.md", "docs/standards/testing.md",
    "docs/standards/git-delivery.md", "docs/templates/README.md",
    "docs/templates/requirement.md", "docs/templates/design.md",
    "docs/templates/plan.md", "docs/templates/report.md",
    "docs/templates/decision.md", "docs/decisions/README.md",
    "docs/research/README.md", "docs/operations/README.md",
}


@dataclass(frozen=True)
class Link:
    line: int
    target: str = ""
    error: str = ""


def mask_examples(source: str) -> str:
    """Mask fenced and inline code without changing line numbers."""
    output = []
    fence = ""
    width = 0
    for line in source.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            closing = marker and marker[1][0] == fence
            if closing and len(marker[1]) >= width and not marker[2].strip():
                fence = ""
            output.append("\n" if line.endswith("\n") else "")
        elif marker:
            fence, width = marker[1][0], len(marker[1])
            output.append("\n" if line.endswith("\n") else "")
        else:
            output.append(line)
    text = "".join(output)
    pattern = re.compile(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)", re.DOTALL)
    return pattern.sub(
        lambda match: "".join("\n" if ch == "\n" else " " for ch in match[0]),
        text,
    )


def balanced_end(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def destination(value: str) -> str:
    value = value.strip()
    if value.startswith("<"):
        end = value.find(">")
        return value[1:end] if end != -1 else value
    return value.split(maxsplit=1)[0] if value else ""


def reference_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def markdown_links(source: str) -> list[Link]:
    text = mask_examples(source)
    references = {}
    definition = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(<[^>]*>|\S+).*$", re.MULTILINE)
    for match in definition.finditer(text):
        references.setdefault(reference_key(match[1]), destination(match[2]))
    text = definition.sub(lambda match: " " * len(match[0]), text)
    links = []
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] != "[":
            i += 1
            continue
        end = balanced_end(text, i, "[", "]")
        if end == -1:
            i += 1
            continue
        label = text[i + 1:end]
        line = text.count("\n", 0, i) + 1
        next_pos = end + 1
        if next_pos < len(text) and text[next_pos] == "(":
            stop = balanced_end(text, next_pos, "(", ")")
            if stop != -1:
                links.append(Link(line, destination(text[next_pos + 1:stop])))
                i = stop + 1
                continue
        reference = re.match(r"[ \t]*(?:\n[ \t]*)?\[([^\]\n]*)\]", text[next_pos:])
        if reference:
            key = reference_key(reference[1] or label)
            if key in references:
                links.append(Link(line, references[key]))
            else:
                links.append(Link(line, error=f"undefined link reference: {key}"))
            i = next_pos + reference.end()
            continue
        key = reference_key(label)
        if key in references:
            links.append(Link(line, references[key]))
        i = end + 1
    return links


def link_issues(root: Path, file: Path) -> list[str]:
    relative = file.relative_to(root).as_posix()
    try:
        source = file.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as error:
        return [f"{relative}: cannot read UTF-8: {error}"]
    errors = []
    for link in markdown_links(source):
        prefix = f"{relative}:{link.line}"
        if link.error:
            errors.append(f"{prefix}: {link.error}")
            continue
        target = re.sub(r"\\([\\`*{}\[\]()#+.!_<>-])", r"\1", link.target)
        if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith(("/", "\\")):
            errors.append(f"{prefix}: absolute local link is forbidden: {target}")
            continue
        if target.casefold().startswith("file:"):
            errors.append(f"{prefix}: file URI is forbidden; use a repository-relative link: {target}")
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        path = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not path:
            continue
        candidate = (file.parent / path).resolve()
        if not candidate.is_relative_to(root.resolve()):
            errors.append(f"{prefix}: link escapes repository: {target}")
        elif any(part in FORBIDDEN_PARTS for part in candidate.relative_to(root.resolve()).parts):
            errors.append(f"{prefix}: link points to local-only/generated state: {target}")
        elif not candidate.exists():
            errors.append(f"{prefix}: missing local target: {target}")
    return errors


def discover_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True,
    )
    if result.returncode:
        raise RuntimeError("git file inventory failed; run inside an initialized repository")
    names = result.stdout.decode("utf-8").split("\0")
    return sorted({root / name for name in names if name and (root / name).is_file()})


def layout_issues(root: Path, files: list[Path]) -> list[str]:
    errors = []
    for file in files:
        path = file.relative_to(root)
        name = path.as_posix()
        if len(path.parts) == 1:
            if name not in ALLOWED_ROOT_FILES:
                errors.append(f"{name}: unexpected root file")
        elif path.parts[0] not in ALLOWED_ROOT_DIRS:
            errors.append(f"{name}: unexpected root directory")
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            errors.append(f"{name}: generated or local-only directory must not be submitted")
        if file.suffix.lower() in ARTIFACT_SUFFIXES:
            errors.append(f"{name}: generated artifact must not be submitted")
        if file.name.startswith(".env") and not file.name.endswith(".example"):
            errors.append(f"{name}: runtime environment configuration must not be submitted")
        if len(path.parts) > 1 and path.parts[0] == "configs":
            if not (file.name == "README.md" or ".example." in file.name
                    or path.parts[1] == "prompts"):
                errors.append(f"{name}: configs must be examples or versioned prompts")
    return errors


def check_docs(root: Path, files: list[Path]) -> list[str]:
    errors = [f"{name}: required file is missing" for name in sorted(REQUIRED_FILES)
              if not (root / name).is_file()]
    errors.extend(layout_issues(root, files))
    docs = [file for file in files if file.suffix.lower() == ".md"]
    for file in docs:
        errors.extend(link_issues(root, file))
    print(f"[docs] Checked {len(docs)} Markdown files and {len(files)} repository files.")
    return errors


def run_command(root: Path, command: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    print(f"[code] {' '.join(command)}", flush=True)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(command, cwd=root, env=environment, text=True,
                          encoding="utf-8", errors="replace", capture_output=capture)


def check_code(root: Path, files: list[Path]) -> list[str]:
    errors = []
    python_files = [file for file in files if file.suffix == ".py"]
    for file in python_files:
        try:
            compile(file.read_text(encoding="utf-8"), str(file), "exec")
        except (SyntaxError, UnicodeError, OSError) as error:
            errors.append(f"{file.relative_to(root)}: Python syntax/encoding error: {error}")
    tooling = root / "tests" / "tooling"
    if tooling.is_dir() and any(tooling.glob("test_*.py")):
        result = run_command(root, [sys.executable, "-B", "-m", "unittest", "discover",
                                   "-s", "tests/tooling", "-p", "test_*.py", "-v"])
        if result.returncode:
            errors.append("Python tooling tests failed")
    else:
        errors.append("Python tooling regression suite is missing")
    other_python = [file for file in python_files
                    if file.relative_to(root).parts[0] not in {"scripts", "tests"}]
    if other_python:
        errors.append("Python business code requires a configured test stage")
    unsupported = [file.relative_to(root).as_posix() for file in files
                   if file.suffix.lower() in UNCONFIGURED_SOURCE_SUFFIXES]
    if unsupported:
        errors.append("Language checks are not configured for: " + ", ".join(unsupported))
    go_files = [file for file in files if file.suffix == ".go"]
    nested_modules = [file for file in files if file.name == "go.mod" and file.parent != root]
    if nested_modules:
        errors.append("Nested Go modules require an explicitly configured check stage")
    if not (root / "go.mod").is_file():
        if go_files:
            errors.append("Go source exists but root go.mod is missing")
        else:
            print("[code] Go business checks: NOT APPLICABLE (no Go module/source).")
        return errors
    if not shutil.which("go") or not shutil.which("gofmt"):
        errors.append("Go module exists but go/gofmt is unavailable")
        return errors
    # Check each file to avoid command-line length limits and skip generated code.
    for file in go_files:
        content = file.read_text(encoding="utf-8")
        if re.search(r"(?m)^// Code generated .* DO NOT EDIT\.$", content):
            continue
        result = run_command(root, ["gofmt", "-l", file.relative_to(root).as_posix()], capture=True)
        if result.returncode or result.stdout.strip():
            errors.append(f"{file.relative_to(root)}: Go format check failed; run gofmt explicitly")
    for command in (["go", "vet", "./..."], ["go", "test", "-count=1", "./..."]):
        if run_command(root, command).returncode:
            errors.append("Command failed: " + " ".join(command))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("docs", "code", "all"), default="all")
    args = parser.parse_args(argv)
    try:
        files = discover_files(ROOT)
        errors = []
        if args.scope in {"docs", "all"}:
            errors.extend(check_docs(ROOT, files))
        if args.scope in {"code", "all"}:
            errors.extend(check_code(ROOT, files))
    except (OSError, UnicodeError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"FAILED: {len(errors)} issue(s).", file=sys.stderr)
        return 1
    print(f"PASS: applicable {args.scope} checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
