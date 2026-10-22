"""Guarded code-change proposal/apply/test pipeline for the local Java project.

Generated code is never executed as a shell command. Only source/test/resource files
under the configured URL-shortener module can be changed. Maven is invoked with a
fixed command, a timeout, and a validated working directory.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILES = 20
MAX_FILE_CHARS = 60_000
ALLOWED_PREFIXES = (
    "services/url-shortener/src/main/java/",
    "services/url-shortener/src/test/java/",
    "services/url-shortener/src/main/resources/",
)


class ImplementationError(RuntimeError):
    pass


_TEST_ANNOTATION_RE = re.compile(
    r"@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b"
)


def _test_annotation_count(source: str) -> int:
    """Count common JUnit 5 test annotations in a Java source file."""
    return len(_TEST_ANNOTATION_RE.findall(source))


def _validate_new_test_case(root: Path, files: list[dict[str, str]]) -> dict[str, Any]:
    """Require the proposal to add at least one JUnit test case, not just run old tests."""
    test_files = [
        item for item in files
        if item["path"].startswith("services/url-shortener/src/test/java/")
        and item["path"].endswith(".java")
    ]
    if not test_files:
        raise ImplementationError(
            "Proposal rejected: include a Java test file under "
            "services/url-shortener/src/test/java/ and add at least one test case."
        )

    added_test_cases = 0
    for item in test_files:
        target = (root / item["path"]).resolve()
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        old_count = _test_annotation_count(existing)
        new_count = _test_annotation_count(item["content"])
        if new_count <= old_count:
            continue
        added_test_cases += new_count - old_count

    if added_test_cases < 1:
        raise ImplementationError(
            "Proposal rejected: no additional JUnit test annotation was detected. "
            "Add a new @Test, @ParameterizedTest, @RepeatedTest, @TestFactory, "
            "or @TestTemplate case before applying."
        )

    return {
        "test_files": [item["path"] for item in test_files],
        "test_cases_added": added_test_cases,
    }


def project_root() -> Path:
    configured = os.getenv("PROJECT_ROOT")
    base = Path(__file__).resolve().parents[3]
    candidate = Path(configured) if configured else base
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    candidate = candidate.resolve()
    if not (candidate / "services" / "url-shortener" / "pom.xml").is_file():
        raise ImplementationError(
            f"PROJECT_ROOT does not contain services/url-shortener/pom.xml: {candidate}"
        )
    return candidate


def parse_changes(raw: str) -> list[dict[str, str]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImplementationError(f"LLM did not return valid JSON: {exc}") from exc

    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise ImplementationError(f"Expected 1-{MAX_FILES} files in JSON field 'files'")

    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("content"), str)
        ):
            raise ImplementationError(
                "Each file must contain string 'path' and 'content' fields"
            )

        name = item["path"].replace("\\", "/")
        posix = PurePosixPath(name)
        if (
            posix.is_absolute()
            or ".." in posix.parts
            or not name.startswith(ALLOWED_PREFIXES)
        ):
            raise ImplementationError(
                f"File path is outside allowed source directories: {name}"
            )
        if name in seen:
            raise ImplementationError(f"Duplicate path: {name}")
        if len(item["content"]) > MAX_FILE_CHARS:
            raise ImplementationError(f"File too large: {name}")
        if name.endswith(".java") and not item["content"].strip():
            raise ImplementationError(f"Empty Java file: {name}")

        seen.add(name)
        result.append({"path": name, "content": item["content"]})

    return result


def propose(
    llm: Any, requirement: str, instructions: str | None = None
) -> dict[str, Any]:
    root = project_root()
    prompt = (
        (
            "Generate actual complete file contents implementing the requirement in this existing Java 21 / Spring Boot 3.4 project. "
            'Return ONLY valid JSON with shape {"files":[{"path":"services/url-shortener/src/main/java/...","content":"complete file text"}]}. '
            "Paths must be relative to repository root and only under services/url-shortener/src/main/java/, services/url-shortener/src/test/java/, "
            "or services/url-shortener/src/main/resources/. Include appropriate unit tests. Do not modify pom.xml, workflows, scripts, configuration secrets, or deployment files. "
            "Do not include markdown fences. Existing project source files are listed here: "
        )
        + "\n"
        + list_source_files(root)
    )
    if instructions:
        prompt += "\nAdditional instructions: " + instructions

    raw = llm.generate(
        "implementation_code_generation",
        "brownfield",
        requirement,
        {"repository_context": prompt},
    )
    files = parse_changes(raw)
    test_summary = _validate_new_test_case(root, files)
    return {
        "files": files,
        **test_summary,
        "file_count": len(files),
        "status": "proposed_not_applied",
        "warning": "Review every generated file before applying. No files have been changed.",
    }


def list_source_files(root: Path) -> str:
    base = root / "services" / "url-shortener" / "src"
    lines: list[str] = []
    for path in sorted(base.rglob("*.java")):
        rel = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            content = ""
        lines.append(f"--- {rel} ---\n{content[:12000]}")
    return "\n".join(lines)[:40000]


def _maven_command() -> tuple[list[str] | str, str, bool]:
    """Resolve Maven and return (command, display command, shell flag).

    On Windows, Maven is usually mvn.cmd, which must be launched through cmd.exe.
    On POSIX systems, invoke the Maven executable directly. The command contains
    only a resolved local executable and fixed arguments, never generated code.
    """
    timeout_value = os.getenv("MAVEN_TEST_TIMEOUT_SECONDS", "300")
    try:
        timeout_seconds = int(timeout_value)
        if timeout_seconds <= 0:
            raise ValueError
    except ValueError as exc:
        raise ImplementationError(
            "MAVEN_TEST_TIMEOUT_SECONDS must be a positive integer"
        ) from exc

    if os.name == "nt":
        executable = (
            os.getenv("MAVEN_CMD")
            or shutil.which("mvn.cmd")
            or shutil.which("mvn")
        )
        if not executable:
            raise ImplementationError(
                "Maven was not found in the orchestrator process PATH. "
                "Set MAVEN_CMD to the full path of mvn.cmd and restart the orchestrator."
            )

        comspec = os.getenv("COMSPEC", "cmd.exe")
        # Pass a raw command line so Python does not escape the nested quotes
        # that cmd.exe needs around the executable path.
        command = f'"{comspec}" /d /s /c ""{executable}" -B -ntp test"'
        return command, f'"{executable}" -B -ntp test', False

    executable = os.getenv("MAVEN_CMD") or shutil.which("mvn")
    if not executable:
        raise ImplementationError(
            "Maven was not found in PATH. Set MAVEN_CMD to the Maven executable."
        )
    return [executable, "-B", "-ntp", "test"], "mvn -B -ntp test", False


def apply_and_test(proposal: dict[str, Any]) -> dict[str, Any]:
    root = project_root()
    module_dir = (root / "services" / "url-shortener").resolve()
    if not (module_dir / "pom.xml").is_file():
        raise ImplementationError(f"Java module pom.xml not found: {module_dir}")

    files = proposal.get("files")
    if not isinstance(files, list) or not files:
        raise ImplementationError("No approved proposal found")

    # Resolve Maven before touching files so a missing executable cannot trigger
    # an unnecessary write/rollback cycle.
    command, display_command, _ = _maven_command()
    timeout_seconds = int(os.getenv("MAVEN_TEST_TIMEOUT_SECONDS", "300"))

    # Validate all paths again at the trust boundary.
    validated = parse_changes(json.dumps({"files": files}))
    test_summary = _validate_new_test_case(root, validated)
    before: dict[Path, bytes | None] = {}
    for item in validated:
        target = (root / item["path"]).resolve()
        if root not in target.parents:
            raise ImplementationError("Resolved path escaped repository root")
        if target.exists() and not target.is_file():
            raise ImplementationError(f"Target path is not a regular file: {target}")
        before[target] = target.read_bytes() if target.exists() else None

    changed: list[str] = []
    try:
        for item in validated:
            target = (root / item["path"]).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8", newline="")
            changed.append(item["path"])

        proc = subprocess.run(
            command,
            cwd=module_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )

        result = {
            "status": (
                "tests_passed" if proc.returncode == 0 else "tests_failed_rolled_back"
            ),
            "exit_code": proc.returncode,
            "changed_files": changed,
            **test_summary,
            "test_command": display_command,
            "stdout_tail": proc.stdout[-12000:],
            "stderr_tail": proc.stderr[-12000:],
        }
        if proc.returncode != 0:
            rollback(before)
            result["rollback_performed"] = True
        else:
            result["rollback_performed"] = False
        return result

    except Exception as exc:
        rollback(before)
        if isinstance(exc, subprocess.TimeoutExpired):
            raise ImplementationError(
                "Maven tests timed out; changed files were rolled back"
            ) from exc
        if isinstance(exc, FileNotFoundError):
            raise ImplementationError(
                "Maven could not be launched; changed files were rolled back. "
                "Check MAVEN_CMD and the orchestrator process PATH."
            ) from exc
        raise ImplementationError(
            f"Implementation failed; changed files were rolled back: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def rollback(before: dict[Path, bytes | None]) -> None:
    for path, content in before.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
