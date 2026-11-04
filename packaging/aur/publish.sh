#!/bin/bash
# Make the AUR's hyprmuse-bin what this checkout's packaging/aur/PKGBUILD gives for the latest
# GitHub release of hyprmuse.
#
#   packaging/aur/publish.sh
#
# Runs update.sh for the latest release on a copy of this directory and compares the resulting
# PKGBUILD and .SRCINFO with those on the AUR's master branch:
#   - the same: does nothing;
#   - different, and pkgver-pkgrel newer than the AUR's: pushes them as one commit (the first
#     push creates the package);
#   - different, but not newer: fails, since helpers would not offer it as an upgrade. A change
#     to the PKGBUILD alone needs it moved to the latest release with update.sh, then pkgrel raised.
# A latest release whose tag is not v<numbers and dots> (a pre-release made latest) is skipped
# with a message. Nothing in this checkout is written. Each run downloads the release's assets.
#
# The environment variable AUR_REPO overrides the git URL compared with and pushed to (default
# ssh://aur@aur.archlinux.org/hyprmuse-bin.git). git reaches the AUR over ssh with whatever key
# and known_hosts GIT_SSH_COMMAND supplies; packaging/aur/Jenkinsfile sets both.
#
# Fails when the latest release cannot be found, when update.sh fails (see its header), when the
# AUR cannot be read or pushed to, or as above. Needs bash, curl, git, sort -V and what
# update.sh needs.

# url is set by sourcing the PKGBUILD, which shellcheck does not follow.
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
[[ $location == */tag/v* ]] \
    || { echo "$0: $url/releases/latest redirects to '$location', not to a release tag" >&2; exit 1; }
version=${location##*/tag/v}
if ! [[ $version =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
    echo "the latest release, v$version, is not a plain version; the AUR stays as it is"
    exit 0
fi

mkdir "$work/pkg"
cp "$here/PKGBUILD" "$here/update.sh" "$work/pkg/"
"$work/pkg/update.sh" "$version"

# The AUR's master branch, which the AUR serves and accepts pushes to whatever its HEAD names.
# A package not yet created has no master: then everything is new.
git init --quiet "$work/aur"
git -C "$work/aur" remote add origin "$aur_repo"
found=0
git -C "$work/aur" ls-remote --exit-code origin refs/heads/master >/dev/null || found=$?
case $found in
    0) if ! git -C "$work/aur" fetch --quiet origin master \
               || ! git -C "$work/aur" checkout --quiet -B master FETCH_HEAD; then
           echo "$0: could not fetch master from $aur_repo" >&2
           exit 1
       fi ;;
    2) ;;
    *) echo "$0: could not read $aur_repo" >&2; exit 1 ;;
esac

if cmp -s "$work/pkg/PKGBUILD" "$work/aur/PKGBUILD" && cmp -s "$work/pkg/.SRCINFO" "$work/aur/.SRCINFO"; then
    echo "the AUR already has this PKGBUILD for v$version"
    exit 0
fi
# Prints pkgver-pkgrel from a .SRCINFO, read rather than sourced: the AUR's copy is not run here.
release_of() {
    sed -n -e 's/^\tpkgver = //p' "$1" | tr '\n' '-'
    sed -n -e 's/^\tpkgrel = //p' "$1"
}
new=$(release_of "$work/pkg/.SRCINFO")
if [ -f "$work/aur/.SRCINFO" ]; then
    old=$(release_of "$work/aur/.SRCINFO")
    # Numeric pkgver and pkgrel, so sort -V orders them as pacman's vercmp does.
    if [ "$new" = "$old" ] || [ "$(printf '%s\n%s\n' "$old" "$new" | sort -V | tail -n 1)" != "$new" ]; then
        echo "$0: the PKGBUILD differs from the AUR's, but $new is not newer than its $old;" \
             "run packaging/aur/update.sh $version, then raise pkgrel in packaging/aur/PKGBUILD" >&2
        exit 1
    fi
fi

cp "$work/pkg/PKGBUILD" "$work/pkg/.SRCINFO" "$work/aur/"
git -C "$work/aur" add PKGBUILD .SRCINFO
git -C "$work/aur" -c user.name='hyprmuse Jenkins' -c user.email='jenkins@hyprmuse.invalid' \
    commit --quiet -m "Update to $new" || { echo "$0: could not commit to the AUR clone" >&2; exit 1; }
git -C "$work/aur" push --quiet origin HEAD:master || { echo "$0: could not push to $aur_repo" >&2; exit 1; }
echo "pushed $new to $aur_repo"
