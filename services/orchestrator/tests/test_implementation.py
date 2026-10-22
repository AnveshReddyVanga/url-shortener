import json
import pytest
import app.implementation as implementation
from app.implementation import parse_changes, ImplementationError


def test_windows_maven_command_quotes_paths_with_spaces(monkeypatch):
    executable = r"C:\Program Files\Apache Maven\bin\mvn.cmd"
    comspec = r"C:\Windows\System32\cmd.exe"
    monkeypatch.setattr(implementation.os, "name", "nt")
    monkeypatch.setenv("MAVEN_CMD", executable)
    monkeypatch.setenv("COMSPEC", comspec)

    command, display_command, shell = implementation._maven_command()

    assert command == f'"{comspec}" /d /s /c ""{executable}" -B -ntp test"'
    assert display_command == f'"{executable}" -B -ntp test'
    assert shell is False


def test_parse_allowed_java_file():
    files = parse_changes(
        json.dumps(
            {
                "files": [
                    {
                        "path": "services/url-shortener/src/main/java/com/example/Test.java",
                        "content": "class Test {}",
                    }
                ]
            }
        )
    )
    assert len(files) == 1


def test_reject_path_traversal():
    with pytest.raises(ImplementationError):
        parse_changes(
            json.dumps(
                {
                    "files": [
                        {
                            "path": "services/url-shortener/src/main/java/../../../../evil.py",
                            "content": "x",
                        }
                    ]
                }
            )
        )


def test_reject_non_allowlisted_path():
    with pytest.raises(ImplementationError):
        parse_changes(json.dumps({"files": [{"path": "pom.xml", "content": "x"}]}))


def test_reject_empty_or_too_many_files():
    with pytest.raises(ImplementationError):
        parse_changes('{"files": []}')
