"""hyprmuse's own release rule: which paths `.release-exempt` lets change without a
version raise, as `scripts/release changed` reads it. The script itself is the
template's and tested there (agent-estate's tests/release_test.py); this pins the
repo's list, so that widening a line (say `packaging/aur` for its PKGBUILD) fails here."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo(tmp_path):
    """A repository holding this checkout's scripts/release and .release-exempt, with
    one commit to diff from."""
    for name in ("scripts/release", ".release-exempt"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, tmp_path / name)
    git(tmp_path, "init", "--quiet")
    git(tmp_path, "add", "--all")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    return tmp_path


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S603, S607
                   cwd=cwd, check=True)


def changed(repo, path):
    """`scripts/release changed`'s exit status for a commit that touches ``path`` alone:
    0 when it is released, 1 when exempt."""
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", path)
    return subprocess.run(["sh", "scripts/release", "changed", "HEAD^"], cwd=repo,  # noqa: S603, S607
                          check=False).returncode


@pytest.mark.parametrize("path", [
    "packaging/aur/Jenkinsfile", "packaging/pypi/Jenkinsfile", "packaging/aur/PKGBUILD",
    "packaging/aur/.SRCINFO", "assets/logo.svg", "README.md", "docs/x.md", "tests/test_x.py"])
def test_a_change_to_an_exempt_path_alone_needs_no_raise(repo, path):
    assert changed(repo, path) == 1


@pytest.mark.parametrize("path", [
    "hyprmuse/cli.py", "quote.py", "uv.lock", "pyproject.toml", "scripts/package",
    "packaging/build-binary.sh", "packaging/aur/update.sh", "packaging/aur/publish.sh",
    "packaging/pypi/publish.sh", "packaging/licenses/README.md"])
def test_a_change_to_a_released_path_needs_the_raise(repo, path):
    assert changed(repo, path) == 0
