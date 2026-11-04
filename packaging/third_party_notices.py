"""Print the license notices of the third-party code the hyprmuse binary bundles.

    pyi-archive_viewer -r -b BINARY | python packaging/third_party_notices.py

Reads the binary's archive listing on stdin and must run in the environment
PyInstaller built it from, whose installed distributions it reads the license files
of; packaging/build-binary.sh runs it so and writes what it prints beside the binary.
The notices cover the Python interpreter, PyInstaller's bootloader, and every installed
distribution other than hyprmuse that provides a top-level package or module the
listing names, including the license files of what that distribution vendors.

It reads only what each distribution ships: the C libraries linked into the
interpreter and into lxml carry no license files there, so their notices are not
included (TODO.md, "The binary's notices leave out its C libraries").

Exits 1, naming each, when a bundled distribution ships no license file, so that a
new dependency cannot reach a release without its notice.
"""

import platform
import re
import sys
import sysconfig
from collections.abc import Iterable
from importlib.metadata import Distribution, distribution, packages_distributions
from pathlib import Path

RULE = "=" * 79


def bundled_distributions(listing: Iterable[str]) -> list[Distribution]:
    """Return the installed distributions an archive listing draws on, sorted by name.

    ``listing`` holds the lines of ``pyi-archive_viewer -r -b``: a module as a dotted
    name, a data file as a path, each possibly indented. The first component of each
    names a top-level package or module; one no installed distribution provides
    (the standard library, PyInstaller's own modules, a heading) is skipped, and so
    is hyprmuse.
    """
    providers = packages_distributions()
    names = set()
    for line in listing:
        top = re.split(r"[./]", line.strip(), maxsplit=1)[0]
        names.update(providers.get(top, []))
    names.discard("hyprmuse")
    return [distribution(name) for name in sorted(names, key=str.lower)]


def license_texts(dist: Distribution) -> list[tuple[str, str]]:
    """Return (path, text) for each license file ``dist`` installed, in RECORD order.

    A license file is one in a ``licenses/`` directory of a dist-info (PEP 639), or,
    for older wheels, one directly in a dist-info whose name starts with LICENSE,
    LICENCE, COPYING or NOTICE. That includes the dist-infos a distribution vendors
    inside its own package. The path is as RECORD gives it, relative to
    site-packages.
    """
    prefixes = ("LICENSE", "LICENCE", "COPYING", "NOTICE")
    texts = []
    for path in dist.files or []:
        parts = path.parts
        dist_info = next((i for i, part in enumerate(parts) if part.endswith(".dist-info")), None)
        if dist_info is None:
            continue
        rest = parts[dist_info + 1 :]
        in_licenses = len(rest) > 1 and rest[0] == "licenses"
        at_top = len(rest) == 1 and rest[0].upper().startswith(prefixes)
        if in_licenses or at_top:
            texts.append((str(path), path.read_text(encoding="utf-8")))
    return texts


def section(title: str, texts: list[tuple[str, str]]) -> str:
    """Return one component's notice: a ruled title, then each file under its path."""
    body = "\n".join(f"--- {name} ---\n\n{text.rstrip()}\n" for name, text in texts)
    return f"{RULE}\n{title}\n{RULE}\n\n{body}"


def main() -> int:
    """Print the notices for the listing on stdin to stdout; return the exit status."""
    python = Path(sysconfig.get_path("stdlib"), "LICENSE.txt")
    sections = [
        section(f"Python {platform.python_version()}",
                [(python.name, python.read_text(encoding="utf-8"))]),
        section("PyInstaller bootloader (GPL-2.0-or-later WITH Bootloader-exception)",
                license_texts(distribution("pyinstaller"))),
    ]
    missing = []
    for dist in bundled_distributions(sys.stdin):
        name = dist.metadata["Name"]
        licensed = dist.metadata.get("License-Expression") or dist.metadata.get("License")
        texts = license_texts(dist)
        if not texts:
            missing.append(name)
        title = f"{name} {dist.version}" + (f" ({licensed})" if licensed else "")
        sections.append(section(title, texts))
    if missing:
        print(f"third_party_notices.py: no license file in {', '.join(missing)}",
              file=sys.stderr)
        return 1
    print("The hyprmuse binary bundles the following third-party software, each under its",
          "own license, reproduced below.\n", sep="\n")
    print("\n".join(sections), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
