#!/bin/bash
# Upload the sdist and wheel of hyprmuse's latest GitHub release to PyPI.
#
#   UV_PUBLISH_TOKEN=pypi-… packaging/pypi/publish.sh
#
# Downloads hyprmuse-<version>.tar.gz and hyprmuse-<version>-py3-none-any.whl from the latest
# release, which Jenkins's Release stage attaches, and hands them to uv publish. A file the index
# already has with the same hash is skipped, so a run after an upload changes nothing; one it has
# with a different hash fails. A release with neither file (made before releases carried them) is
# skipped with a message.
#
# uv publish reads its token and URLs from the environment: UV_PUBLISH_TOKEN, and
# UV_PUBLISH_URL and UV_PUBLISH_CHECK_URL, which default here to PyPI's upload API and simple
# index. Tests point both at a local index. packaging/pypi/Jenkinsfile sets the token.
#
# Fails when the latest release cannot be found, when a download fails or only one of the two
# files exists, or when uv publish fails. Needs bash, curl and uv.
set -euo pipefail

repo_url=https://github.com/DavidSiegl/hyprmuse
export UV_PUBLISH_URL=${UV_PUBLISH_URL:-https://upload.pypi.org/legacy/}
export UV_PUBLISH_CHECK_URL=${UV_PUBLISH_CHECK_URL:-https://pypi.org/simple/}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# GitHub redirects releases/latest to releases/tag/v<version>.
location=$(curl -fsS -o /dev/null -w '%{redirect_url}' "$repo_url/releases/latest") \
    || { echo "$0: could not ask $repo_url for its latest release" >&2; exit 1; }
[[ $location == */tag/v* ]] \
    || { echo "$0: $repo_url/releases/latest redirects to '$location', not to a release tag" >&2; exit 1; }
version=${location##*/tag/v}

# Each file, downloaded into $work; 404 means the release does not carry it.
missing=()
for file in "hyprmuse-$version.tar.gz" "hyprmuse-$version-py3-none-any.whl"; do
    status=$(curl -sSL -o "$work/$file" -w '%{http_code}' "$repo_url/releases/download/v$version/$file") \
        || { echo "$0: could not download $file" >&2; exit 1; }
    case $status in
        200) ;;
        404) missing+=("$file"); rm -f "$work/$file" ;;
        *) echo "$0: $file answered HTTP $status" >&2; exit 1 ;;
    esac
done
case ${#missing[@]} in
    0) ;;
    2) echo "release v$version carries no sdist or wheel; nothing to upload"; exit 0 ;;
    *) echo "$0: release v$version carries no ${missing[0]}" >&2; exit 1 ;;
esac

uv publish "$work"/hyprmuse-* || { echo "$0: uv publish failed for v$version" >&2; exit 1; }
echo "PyPI has v$version"
