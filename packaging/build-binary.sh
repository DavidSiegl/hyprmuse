#!/bin/sh
# Build dist/hyprmuse-linux-<arch>, a PyInstaller one-file binary of the hyprmuse command with Python and its
# dependencies inside, write its .sha256 beside it and the licenses of what it bundles to
# dist/hyprmuse-third-party-licenses.txt, and smoke-test it offline. Jenkins's Package stage runs it on every
# build, and its Release stage attaches what it builds. Linux only, since hyprlock is. The binary links the C
# library of the machine it was built on, so it runs on that glibc or a newer one.
set -eu

cd "$(dirname "$0")/.."

[ "$(uname -s)" = Linux ] || { echo "build-binary.sh: no binary is built for $(uname -s)" >&2; exit 1; }
case "$(uname -m)" in
    x86_64 | amd64) arch=x86_64 ;;
    arm64 | aarch64) arch=arm64 ;;
    *) echo "build-binary.sh: no binary is built for $(uname -m)" >&2; exit 1 ;;
esac
name="hyprmuse-linux-$arch"
bin="dist/$name"

# The build group holds PyInstaller. --paths . puts the package on the import path of
# hyprmuse/__main__.py, which PyInstaller analyses as a script outside it.
uv run --frozen --group build pyinstaller --onefile --name "$name" --noconfirm --clean --paths . \
    --distpath dist --workpath build/pyinstaller --specpath build/pyinstaller hyprmuse/__main__.py

(cd dist && sha256sum "$name" > "$name.sha256")

# What only harvesting needs, which no offline run reaches: requests reads certifi's CA
# bundle at the first HTTPS request. So it must be in the archive by name.
contents=$(uv run --frozen --group build pyi-archive_viewer -r -b "$bin")
printf '%s\n' "$contents" | grep -q "^ *certifi/cacert.pem" \
    || { echo "build-binary.sh: $bin bundles no certifi/cacert.pem" >&2; exit 1; }
# bs4 imports lxml whenever it is installed, so a dependency or a stale venv that brings it back would bundle
# it again unnoticed; packaging/licenses/README.md says why it must stay out.
if printf '%s\n' "$contents" | grep -q "^ *lxml/"; then
    echo "build-binary.sh: $bin bundles lxml" >&2; exit 1
fi

printf '%s\n' "$contents" | uv run --frozen --group build python packaging/third_party_notices.py \
    > dist/hyprmuse-third-party-licenses.txt

# The smoke test runs against a library of its own, so it neither reads nor writes the builder's.
home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT
mkdir -p "$home/data/hyprmuse/subjects"
cat > "$home/data/hyprmuse/subjects/smoke--test.json" <<'EOF'
{"schema": 1, "source": "smoke", "source_id": "test", "name": "Smoke Test", "domain": "poetry",
 "items": [{"work": "Build", "atomic": true, "lines": ["the binary starts and quotes"]}]}
EOF
echo "smoke test: $bin --help"
"$bin" --help >/dev/null
echo "smoke test: $bin quote"
# Captured rather than piped, so that set -e sees the binary's own exit status.
quote=$(XDG_DATA_HOME="$home/data" XDG_CONFIG_HOME="$home/config" "$bin" quote --seed 1)
case "$quote" in
    *'the binary starts and quotes'*) ;;
    *) echo "build-binary.sh: $bin quote printed: $quote" >&2; exit 1 ;;
esac

echo "built $bin, $bin.sha256 and dist/hyprmuse-third-party-licenses.txt"
