#!/bin/bash
# Point packaging/aur/PKGBUILD at GitHub release v<version> and regenerate .SRCINFO beside it.
#
#   packaging/aur/update.sh <version>     e.g. 0.3.1, without the v
#
# Sets pkgver to <version> and sha256sums to the hashes of the sources the PKGBUILD names for that
# version, downloaded from GitHub. pkgrel goes back to 1 when pkgver changes and is kept otherwise,
# so after editing the PKGBUILD alone, raise pkgrel and run this with the same version to refresh
# .SRCINFO. Each release asset is checked against the release's <asset>.sha256 where one exists.
#
# Fails, changing nothing, when a download fails, when an asset's hash differs from its .sha256,
# when no asset has a .sha256 to check, or when the PKGBUILD sets a field srcinfo below does not
# write. Needs bash, curl and sha256sum, not Arch: .SRCINFO is written here rather than by
# makepkg --printsrcinfo. publish.sh pushes the two files to the AUR's hyprmuse-bin repository.

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
current=$(source PKGBUILD && printf '%s' "$pkgver") || { echo "$0: could not read PKGBUILD" >&2; exit 1; }
if [ "$current" = "$version" ]; then
    sed -e "s/^pkgver=.*/pkgver=$version/" PKGBUILD > "$work/PKGBUILD"
else
    sed -e "s/^pkgver=.*/pkgver=$version/" -e 's/^pkgrel=.*/pkgrel=1/' PKGBUILD > "$work/PKGBUILD"
fi

# Each source's sha256, in the order of source=(...), which is the order sha256sums must have.
mapfile -t urls < <(source "$work/PKGBUILD" && for s in "${source[@]}"; do printf '%s\n' "${s#*::}"; done)
[ ${#urls[@]} -gt 0 ] || { echo "$0: found no sources in PKGBUILD" >&2; exit 1; }
sums=()
checked=0
for url in "${urls[@]}"; do
    curl -fsSL -o "$work/download" "$url" || { echo "$0: could not download $url" >&2; exit 1; }
    sums+=("$(sha256sum "$work/download" | cut -d' ' -f1)")
    # A release asset with no .sha256 beside it (404) is not checked; any other failure stops.
    if [[ $url == */releases/download/* ]]; then
        status=$(curl -sSL -o "$work/published" -w '%{http_code}' "$url.sha256") \
            || { echo "$0: could not download $url.sha256" >&2; exit 1; }
        case $status in
            200)
                published=$(cut -d' ' -f1 "$work/published")
                [ "${sums[-1]}" = "$published" ] \
                    || { echo "$0: $url hashes to ${sums[-1]}, but its .sha256 says $published" >&2; exit 1; }
                checked=$((checked + 1)) ;;
            404) ;;
            *) echo "$0: $url.sha256 answered HTTP $status" >&2; exit 1 ;;
        esac
    fi
done
[ "$checked" -gt 0 ] || { echo "$0: no release asset has a .sha256 to check its hash against" >&2; exit 1; }

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
# Writes only the fields in its list, and fails naming any other PKGBUILD field that is set, so
# that a field the PKGBUILD starts using must be added here (in makepkg's order) before it ships.
srcinfo() {
    local field value
    for field in epoch install changelog groups checkdepends makedepends optdepends replaces backup \
            options validpgpkeys noextract md5sums sha1sums sha224sums sha384sums sha512sums b2sums \
            cksums $(compgen -v | grep -E '_(x86_64|aarch64|i686|armv7h|pentium4)$' || true); do
        if declare -p "$field" >/dev/null 2>&1; then
            echo "$0: srcinfo does not write the PKGBUILD's $field; add it" >&2
            return 1
        fi
    done
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
