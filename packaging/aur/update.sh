#!/bin/bash
# Point packaging/aur/PKGBUILD at GitHub release v<version> and regenerate .SRCINFO beside it.
#
#   packaging/aur/update.sh <version>     e.g. 0.3.1, without the v
#
# Sets pkgver to <version>, pkgrel to 1 and sha256sums to the hashes of the sources the PKGBUILD
# names for that version, downloaded from GitHub. Fails, changing nothing, when a download fails or
# when the binary's hash differs from the release's own hyprmuse-linux-x86_64.sha256. Needs bash,
# curl and sha256sum, not Arch: .SRCINFO is written here rather than by makepkg --printsrcinfo,
# and holds only the fields this PKGBUILD sets (see srcinfo below). Pushing the two files to the
# AUR's hyprmuse-bin repository is a separate step.

# pkgname, source and the other fields are set by sourcing the PKGBUILD, which shellcheck does not follow.
# shellcheck disable=SC2154,SC1091
set -euo pipefail

if [ $# -ne 1 ] || ! [[ $1 =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
    echo "usage: $0 <version>, e.g. 0.3.1" >&2
    exit 2
fi
version=$1
cd "$(dirname "$0")"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# The PKGBUILD with the new pkgver and pkgrel, its sums still the old ones.
sed -e "s/^pkgver=.*/pkgver=$version/" -e 's/^pkgrel=.*/pkgrel=1/' PKGBUILD > "$work/PKGBUILD"

# Each source's sha256, in the order of source=(...), which is the order sha256sums must have.
mapfile -t urls < <(source "$work/PKGBUILD" && for s in "${source[@]}"; do printf '%s\n' "${s#*::}"; done)
sums=()
for url in "${urls[@]}"; do
    curl -fsSL -o "$work/download" "$url" || { echo "$0: could not download $url" >&2; exit 1; }
    sums+=("$(sha256sum "$work/download" | cut -d' ' -f1)")
    if [[ $url == */hyprmuse-linux-x86_64 ]]; then
        published=$(curl -fsSL "$url.sha256" | cut -d' ' -f1) \
            || { echo "$0: could not download $url.sha256" >&2; exit 1; }
        [ "${sums[-1]}" = "$published" ] \
            || { echo "$0: $url hashes to ${sums[-1]}, but its .sha256 says $published" >&2; exit 1; }
    fi
done

# Replace the sha256sums=(...) block, one sum per line, aligned as the PKGBUILD writes it.
awk -v sums="${sums[*]}" '
    /^sha256sums=\(/ {
        n = split(sums, s, " ")
        for (i = 1; i <= n; i++)
            printf "%s'\''%s'\''%s\n", (i == 1 ? "sha256sums=(" : "            "), s[i], (i == n ? ")" : "")
        skipping = !/\)/
        next
    }
    skipping { if (/\)/) skipping = 0; next }
    { print }
' "$work/PKGBUILD" > "$work/PKGBUILD.new"

# Prints .SRCINFO for the PKGBUILD in the current shell, in makepkg --printsrcinfo's field order.
# Covers the fields this PKGBUILD sets; one it starts setting (makedepends, optdepends, backup, …)
# must be added here too.
srcinfo() {
    local field value
    printf 'pkgbase = %s\n' "$pkgname"
    for field in pkgdesc pkgver pkgrel url arch license depends provides conflicts source sha256sums; do
        local -n values=$field
        for value in "${values[@]}"; do
            printf '\t%s = %s\n' "$field" "$value"
        done
        unset -n values
    done
    printf '\npkgname = %s\n' "$pkgname"
}
(source "$work/PKGBUILD.new" && srcinfo) > "$work/.SRCINFO"

mv "$work/PKGBUILD.new" PKGBUILD
mv "$work/.SRCINFO" .SRCINFO
echo "PKGBUILD and .SRCINFO now package v$version"
