#!/bin/sh
# Exit 0 when the release version at HEAD, pyproject.toml's [project] version, is greater
# than that of $CHANGE_TARGET, the branch a pull request build merges into, fetched from
# origin first; or when the change since their merge base touches only docs, tests, CI or
# repository tooling (NOT_RELEASED below), saying so on standard output. Exit non-zero,
# saying why on standard error, when it is not, or when either version cannot be read.
# Versions are compared as sort -V orders them, number by number, so 0.10.0 is greater
# than 0.9.0. Jenkins's Version stage runs it on a pull request build into main: the
# Release stage releases a merge into main only when its version has no release yet, so a
# merge that kept main's version would go unreleased, which is what a change to exempt
# paths alone should do. Ported from octoflow-ai's ci/version-raised.sh.
set -eu
: "${CHANGE_TARGET:?is unset; only a pull request build has a target}"
git fetch --quiet origin "+refs/heads/$CHANGE_TARGET:refs/remotes/origin/$CHANGE_TARGET"

# The version of pyproject.toml's [project] table, read from standard input; nothing when
# it has none.
project_version() {
    sed -n '/^\[project\]$/,/^\[/s/^version = "\([^"]*\)"$/\1/p' | head -n 1
}

# The paths whose changes reach no user, as git pathspecs: docs, tests, CI and repository
# tooling. A change to any other path, or a diff that fails, needs the version raised, so
# a path left off errs towards a raise. Markdown counts as docs only at the top level and
# under docs/: packaging/licenses/README.md ships in the binary. assets/ holds the logo
# the README links from main, in no release asset. Each Jenkinsfile is CI. The AUR
# package's PKGBUILD and .SRCINFO reach users without a release: the hyprmuse-aur job
# publishes them for the latest one with pkgrel raised (packaging/aur/publish.sh). The
# rest of packaging/ builds or describes what users install.
NOT_RELEASED=":(exclude)docs :(exclude,glob)*.md :(exclude)tests :(exclude)scripts
:(exclude)Jenkinsfile :(exclude)packaging/aur/Jenkinsfile :(exclude)packaging/pypi/Jenkinsfile
:(exclude)packaging/aur/PKGBUILD :(exclude)packaging/aur/.SRCINFO
:(exclude).github :(exclude).gitignore :(exclude).copier-answers.yml :(exclude)assets"
base=$(git merge-base HEAD "origin/$CHANGE_TARGET")
# shellcheck disable=SC2086 # NOT_RELEASED is split into one pathspec per word on purpose.
if git diff --quiet "$base" HEAD -- . $NOT_RELEASED; then
    echo "version-raised.sh: the change since $CHANGE_TARGET changes only docs, tests, CI" \
        "or repository tooling; nothing to release"
    exit 0
fi

# Read apart from the parse: sh has no pipefail, so a failing git show in a pipeline
# would read as "no version" instead of stopping the script.
target_text=$(git show "origin/$CHANGE_TARGET:pyproject.toml")
target=$(printf '%s\n' "$target_text" | project_version)
head=$(project_version < pyproject.toml)
if [ -z "$target" ] || [ -z "$head" ]; then
    echo "version-raised.sh: no [project] version in pyproject.toml, here ('$head')" \
        "or on $CHANGE_TARGET ('$target')" >&2
    exit 1
fi
greater=$(printf '%s\n%s\n' "$target" "$head" | sort -V | tail -n 1)
if [ "$head" = "$target" ] || [ "$greater" != "$head" ]; then
    echo "version-raised.sh: pyproject.toml's version is $head, not greater than" \
        "$CHANGE_TARGET's $target; raise it with uv version --bump, or the merge goes" \
        "unreleased (Jenkinsfile, Release)" >&2
    exit 1
fi
