"""Print the license notices of the third-party code the hyprmuse binary bundles.

    pyi-archive_viewer -r -b BINARY | python packaging/third_party_notices.py

Reads the binary's archive listing on stdin and must run in the environment
PyInstaller built it from, whose installed distributions it reads the license files
of; packaging/build-binary.sh runs it so and writes what it prints beside the binary.
The notices cover:

- the Python interpreter and the C libraries linked into it, and the C libraries
  linked into lxml, from packaging/licenses/ (NATIVE_NOTICES);
- PyInstaller's bootloader;
- every installed distribution other than hyprmuse that provides a top-level package
  or module the listing names, including the license files of what it vendors.

Exits 1, naming each, when a bundled component has no license file to reproduce, so
that a new dependency cannot reach a release without its notice; and when Python's
minor version or lxml's version is not the one packaging/licenses/ was taken for
(NOTICED_PYTHON, NOTICED_LXML), since another may link other C libraries.
"""

import platform
import re
import sys
from collections.abc import Iterable
from importlib.metadata import (
    Distribution,
    PackagePath,
    distribution,
    packages_distributions,
)
from pathlib import Path

RULE = "=" * 79

# The license texts of the code no distribution carries a license file for: what
# python-build-standalone links into the interpreter, and what lxml's wheels link
# statically. packaging/licenses/README.md says where each came from.
NATIVE_LICENSES = Path(__file__).parent / "licenses"

# The Python minor version and lxml version packaging/licenses/ was taken for.
NOTICED_PYTHON = "3.14"
NOTICED_LXML = "6.0.2"

# (title, files in NATIVE_LICENSES) per component, in the order the notices list them.
NATIVE_NOTICES = [
    (f"Python {NOTICED_PYTHON}, and the software it incorporates",
     ["cpython.txt", "cpython-incorporated.rst"]),
    ("HACL*, in Python's hashlib modules", ["hacl.txt"]),
    ("OpenSSL 3, linked into Python", ["openssl.txt"]),
    ("libffi, linked into Python", ["libffi.txt"]),
    ("Expat, linked into Python", ["expat.txt"]),
    ("SQLite, linked into Python", ["sqlite.txt"]),
    ("bzip2, linked into Python", ["bzip2.txt"]),
    ("liblzma (XZ Utils), linked into Python", ["liblzma.txt"]),
    ("Zstandard, linked into Python", ["zstd.txt"]),
    ("mpdecimal, linked into Python", ["mpdecimal.txt"]),
    ("libuuid, linked into Python", ["libuuid.txt"]),
    ("ncurses, linked into Python", ["ncurses.txt"]),
    ("libedit, linked into Python", ["libedit.txt"]),
    ("zlib, linked into Python and into lxml", ["zlib.txt"]),
    ("libxml2, linked into lxml", ["libxml2.txt"]),
    ("libxslt and libexslt, linked into lxml", ["libxslt.txt"]),
    ("GNU libiconv, linked into lxml", ["libiconv.txt"]),
]


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
    site-packages. Raises ValueError, naming the file, for one that is not UTF-8.
    """
    license_file = re.compile(
        r"(^|/)[^/]+\.dist-info/(licenses/.+|(?i:licen[cs]e|copying|notice)[^/]*)$")
    return [(str(path), read_utf8(path)) for path in dist.files or []
            if license_file.search(path.as_posix())]


def read_utf8(path: Path | PackagePath) -> str:
    """Return the text of ``path``; raise ValueError naming it when it is not UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as err:
        raise ValueError(f"{path} is not UTF-8: {err}") from err


def section(title: str, texts: list[tuple[str, str]]) -> str:
    """Return one component's notice: a ruled title, then each file under its path."""
    body = "\n".join(f"--- {name} ---\n\n{text.rstrip()}\n" for name, text in texts)
    return f"{RULE}\n{title}\n{RULE}\n\n{body}"


def main() -> int:
    """Print the notices for the listing on stdin to stdout; return the exit status."""
    python = ".".join(platform.python_version_tuple()[:2])
    lxml = distribution("lxml").version
    if (python, lxml) != (NOTICED_PYTHON, NOTICED_LXML):
        print(f"third_party_notices.py: packaging/licenses/ holds the C library notices of "
              f"Python {NOTICED_PYTHON} and lxml {NOTICED_LXML}, but this build has Python "
              f"{python} and lxml {lxml}; packaging/licenses/README.md says how to refresh "
              "them", file=sys.stderr)
        return 1
    # (title, license files) per component, in the order the notices list them.
    components = [
        (title, [(f"packaging/licenses/{name}", read_utf8(NATIVE_LICENSES / name))
                 for name in names])
        for title, names in NATIVE_NOTICES
    ]
    components.append(("PyInstaller bootloader (GPL-2.0-or-later WITH Bootloader-exception)",
                       license_texts(distribution("pyinstaller"))))
    for dist in bundled_distributions(sys.stdin):
        # Only the SPDX field: the older License field often holds a whole license text.
        expression = dist.metadata.get("License-Expression")
        title = f"{dist.metadata['Name']} {dist.version}"
        components.append((f"{title} ({expression})" if expression else title,
                           license_texts(dist)))
    missing = [title for title, texts in components if not texts]
    if missing:
        print(f"third_party_notices.py: no license file for {'; '.join(missing)}",
              file=sys.stderr)
        return 1
    print("The hyprmuse binary bundles the following third-party software, each under its",
          "own license, reproduced below.\n", sep="\n")
    print("\n".join(section(title, texts) for title, texts in components), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
