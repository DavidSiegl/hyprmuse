"""scripts/version-raised.sh, which fails a pull request build into main that does
not raise the release version: run in a repository of its own whose origin's main
holds a version, on a branch that changes it."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "version-raised.sh"


def pyproject(version):
    """A pyproject.toml whose [project] has ``version``, between tables whose own
    version lines must not be taken for it."""
    return (f'[tool.other]\nversion = "9.9.9"\n\n[project]\nname = "p"\n'
            f'version = "{version}"\n\n[tool.x]\nversion = "8"\n')


class Repo:
    """A repository on branch ``change``, cut from a main that origin also holds,
    with pyproject.toml at 0.9.0 there."""

    def __init__(self, root: Path):
        self.path = root / "repo"
        origin = root / "origin.git"
        self.path.mkdir()
        self.git("init", "--quiet", "--bare", str(origin), cwd=root)
        self.git("init", "--quiet", "--initial-branch", "main")
        self.commit({"pyproject.toml": pyproject("0.9.0")}, "base")
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "--quiet", "origin", "main")
        self.git("switch", "--quiet", "-c", "change")

    def git(self, *args, cwd=None):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",  # noqa: S607
                        *args], cwd=cwd or self.path, check=True)

    def commit(self, files, message):
        for name, text in files.items():
            path = self.path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)

    def check(self):
        """The script's run at HEAD, as a pull request build into main runs it."""
        env = {**os.environ, "CHANGE_TARGET": "main"}
        return subprocess.run(["sh", str(SCRIPT)], cwd=self.path, env=env,  # noqa: S603, S607
                              capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path)


@pytest.mark.parametrize("version", ["0.9.1", "0.10.0", "1.0.0"])
def test_a_raised_version_passes_compared_number_by_number(repo, version):
    repo.commit({"pyproject.toml": pyproject(version), "hyprmuse/cli.py": "x"}, version)
    proc = repo.check()
    assert (proc.returncode, proc.stderr) == (0, "")


@pytest.mark.parametrize("version", ["0.9.0", "0.8.9"])
def test_a_kept_or_lowered_version_fails_naming_both(repo, version):
    repo.commit({"pyproject.toml": pyproject(version), "hyprmuse/cli.py": "x"}, version)
    proc = repo.check()
    assert proc.returncode != 0
    assert f"version is {version}, not greater than main's 0.9.0" in proc.stderr


def test_a_change_to_docs_tests_ci_or_repository_tooling_alone_passes(repo):
    only = ["docs/agents/README.md", "README.md", "TODO.md", "CLAUDE.md",
            "tests/test_x.py", "scripts/gate", "Jenkinsfile", "packaging/aur/Jenkinsfile",
            "packaging/pypi/Jenkinsfile", ".github/workflows/automerge.yml",
            ".gitignore", ".copier-answers.yml", "assets/logo.svg"]
    repo.commit(dict.fromkeys(only, "x"), "docs, tests, CI and repository tooling")
    proc = repo.check()
    assert (proc.returncode, proc.stderr) == (0, "")
    assert "changes only docs, tests, CI or repository tooling" in proc.stdout


@pytest.mark.parametrize("path", [
    "hyprmuse/cli.py", "quote.py", "uv.lock", "packaging/build-binary.sh",
    "packaging/aur/PKGBUILD", "packaging/licenses/README.md"])
def test_a_change_that_also_touches_released_code_still_needs_the_raise(repo, path):
    repo.commit({"docs/notes.md": path, path: "x"}, path)
    proc = repo.check()
    assert proc.returncode != 0
    assert "version is 0.9.0, not greater than main's 0.9.0" in proc.stderr


def test_a_pyproject_without_a_project_version_fails(repo):
    repo.commit({"pyproject.toml": '[project]\nname = "p"\n'}, "no version")
    proc = repo.check()
    assert proc.returncode != 0
    assert "no [project] version in pyproject.toml" in proc.stderr
