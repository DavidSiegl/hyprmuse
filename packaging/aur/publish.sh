#!/bin/bash
# Bring the AUR's hyprmuse-bin up to the latest GitHub release of hyprmuse.
#
#   packaging/aur/publish.sh
#
# Does nothing when the AUR package's .SRCINFO already has the latest release's pkgver. Otherwise
# runs update.sh for that version on a copy of this directory and pushes the resulting PKGBUILD
# and .SRCINFO to the AUR's master branch as one commit. The first push creates the package.
# This repository's PKGBUILD is the source of truth: whatever was edited in the AUR's copy is replaced.
# Nothing in this checkout is written.
#
# The environment variable AUR_REPO overrides the git URL pushed to (default
# ssh://aur@aur.archlinux.org/hyprmuse-bin.git); tests point it at a local repository. git
# reaches the AUR over ssh with whatever key and known_hosts GIT_SSH_COMMAND supplies;
# packaging/aur/Jenkinsfile sets both.
#
# Fails when the latest release cannot be found, when update.sh fails (see its header), or
# when the clone or push fails. Needs bash, curl, git and what update.sh needs.

# pkgname and url are set by sourcing the PKGBUILD, which shellcheck does not follow.
# shellcheck disable=SC2154,SC1091
set -euo pipefail

aur_repo=${AUR_REPO:-ssh://aur@aur.archlinux.org/hyprmuse-bin.git}
here=$(cd "$(dirname "$0")" && pwd)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# GitHub redirects releases/latest to releases/tag/v<version>.
url=$(source "$here/PKGBUILD" && printf '%s' "$url") || { echo "$0: could not read PKGBUILD" >&2; exit 1; }
location=$(curl -fsS -o /dev/null -w '%{redirect_url}' "$url/releases/latest") \
    || { echo "$0: could not ask $url for its latest release" >&2; exit 1; }
version=${location##*/tag/v}
[[ $location == */tag/v* && $version =~ ^[0-9]+(\.[0-9]+)*$ ]] \
    || { echo "$0: $url/releases/latest redirects to '$location', not to a release tag" >&2; exit 1; }

git clone --quiet "$aur_repo" "$work/aur" || { echo "$0: could not clone $aur_repo" >&2; exit 1; }
if [ -f "$work/aur/.SRCINFO" ] && grep -qxF $'\tpkgver = '"$version" "$work/aur/.SRCINFO"; then
    echo "the AUR already packages v$version"
    exit 0
fi

mkdir "$work/pkg"
cp "$here/PKGBUILD" "$here/.SRCINFO" "$here/update.sh" "$work/pkg/"
"$work/pkg/update.sh" "$version"
cp "$work/pkg/PKGBUILD" "$work/pkg/.SRCINFO" "$work/aur/"

git -C "$work/aur" add PKGBUILD .SRCINFO
git -C "$work/aur" -c user.name='hyprmuse Jenkins' -c user.email='jenkins@hyprmuse.invalid' \
    commit --quiet -m "Update to $version" || { echo "$0: could not commit to the AUR clone" >&2; exit 1; }
git -C "$work/aur" push --quiet origin HEAD:master || { echo "$0: could not push to $aur_repo" >&2; exit 1; }
echo "pushed v$version to $aur_repo"
