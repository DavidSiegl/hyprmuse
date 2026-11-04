#!/bin/bash
# Build hyprmuse's latest GitHub release from source and upload its sdist and wheel to PyPI.
#
#   UV_PUBLISH_TOKEN=pypi-… packaging/pypi/publish.sh
#
# Run from a clone of the repository. Takes the tag v<version> that the latest release names,
# requires its commit to be on origin/main (so a release made at an unreviewed commit is never
# published), builds that commit with uv build in a scratch directory, and requires the build
# to be hyprmuse-<version>.tar.gz and hyprmuse-<version>-py3-none-any.whl (so the commit's
# pyproject.toml has the tag's version). Nothing a release carries is uploaded: whoever can
# create a release can attach files to it. A run that finds both files listed on the index stops
# before building; uv publish skips a file the index already has with the same hash and fails on
# one with a different hash.
#
# uv publish reads its token and URLs from the environment: UV_PUBLISH_TOKEN, and
# UV_PUBLISH_URL and UV_PUBLISH_CHECK_URL, which default here to PyPI's upload API and simple
# index. packaging/pypi/Jenkinsfile sets the token.
#
# Fails when the latest release cannot be found, its tag is not on main, the build fails or
# gives other files, or uv publish fails. Needs bash, curl, git, tar and uv.
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
tag=v$version

# Both files listed on the index's page for hyprmuse means this release is done. Checked before
# building, since a later build may differ by its tools' versions and would then fail to upload.
wheel=hyprmuse-$version-py3-none-any.whl
sdist=hyprmuse-$version.tar.gz
status=$(curl -sSL -o "$work/index.html" -w '%{http_code}' "${UV_PUBLISH_CHECK_URL%/}/hyprmuse/") \
    || { echo "$0: could not read ${UV_PUBLISH_CHECK_URL%/}/hyprmuse/" >&2; exit 1; }
case $status in
    200) if grep -qF ">$wheel<" "$work/index.html" && grep -qF ">$sdist<" "$work/index.html"; then
             echo "the index already has $tag"
             exit 0
         fi ;;
    404) ;;  # no release of hyprmuse uploaded yet
    *) echo "$0: ${UV_PUBLISH_CHECK_URL%/}/hyprmuse/ answered HTTP $status" >&2; exit 1 ;;
esac

# The tag's commit, resolved once, so a tag moved after the check cannot change what is built.
git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main" "+refs/tags/$tag:refs/tags/$tag" \
    || { echo "$0: could not fetch main and $tag from origin" >&2; exit 1; }
commit=$(git rev-parse --verify "refs/tags/$tag^{commit}") \
    || { echo "$0: $tag names no commit" >&2; exit 1; }
git merge-base --is-ancestor "$commit" refs/remotes/origin/main \
    || { echo "$0: $tag is at $commit, which is not on main; not publishing it" >&2; exit 1; }

mkdir "$work/src"
git archive "$commit" | tar -x -C "$work/src" || { echo "$0: could not export $commit" >&2; exit 1; }
uv build --quiet --out-dir "$work/dist" "$work/src" || { echo "$0: uv build failed for $tag" >&2; exit 1; }
built=$(cd "$work/dist" && LC_ALL=C ls)
want=$(printf '%s\n' "$wheel" "$sdist")
[ "$built" = "$want" ] || { echo "$0: building $tag gave $(echo "$built" | tr '\n' ' '), not $(echo "$want" | tr '\n' ' ')" >&2; exit 1; }

uv publish "$work/dist"/* || { echo "$0: uv publish failed for $tag" >&2; exit 1; }
echo "the index has $tag"
