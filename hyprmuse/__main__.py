"""Run the hyprmuse command: `python -m hyprmuse`, and the release binary's entry point.

The import is absolute because packaging/build-binary.sh hands this file to PyInstaller
as a plain script, outside the package, where a relative import has no parent.
"""

from hyprmuse.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
