// Builds main and every pull request in a Multibranch Pipeline job and runs the quality
// gate (scripts/gate) on each, failing the build on GATE: ERROR or when the gate could not
// judge. For a pull request, Jenkins's GitHub App reports the result as the commit status
// continuous-integration/jenkins/pr-head, which auto-merge trusts only from that App, as
// does the ci-cd ruleset on main once agent-estate's init/github-rules.py has set it.
// docs/agents/README.md says how a pull request then merges; the agent-estate README,
// "Jenkins", says what the job and the agent need.
pipeline {
    // Builds run code agents wrote: only on agents that hold nothing an agent should not
    // have. Jenkins enforces that per node (Job Restrictions plugin), not this label.
    agent { label 'untrusted' }

    options {
        buildDiscarder(logRotator(numToKeepStr: '30'))
        timeout(time: 60, unit: 'MINUTES')
    }

    environment {
        UV_NO_PROGRESS = '1'
    }

    stages {
        stage('Install') {
            steps {
                sh 'uv sync --frozen'
                script {
                    // The version a release on main is tagged with.
                    env.PROJECT_VERSION = sh(returnStdout: true, script: '''
                        uv run --frozen python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'
                    ''').trim()
                }
            }
        }

        stage('Gate') {
            steps {
                script {
                    def base
                    if (env.CHANGE_TARGET) {
                        // A pull request: everything since it left its target branch.
                        base = sh(returnStdout: true, script: '''
                            git fetch --quiet origin "+refs/heads/$CHANGE_TARGET:refs/remotes/origin/$CHANGE_TARGET"
                            git merge-base HEAD "origin/$CHANGE_TARGET"
                        ''').trim()
                    } else {
                        // A branch build: since the last successful build, or the last commit when
                        // there is none or a force-push removed it.
                        def previous = env.GIT_PREVIOUS_SUCCESSFUL_COMMIT
                        def kept = previous && sh(returnStatus: true,
                                                  script: 'git cat-file -e "$GIT_PREVIOUS_SUCCESSFUL_COMMIT^{commit}"') == 0
                        base = kept ? previous : 'HEAD^1'
                    }
                    // The base reaches the shell as an environment variable, never as Groovy-built shell code.
                    def status
                    withEnv(["GATE_BASE=${base}"]) {
                        status = sh(returnStatus: true, script: 'scripts/gate "$GATE_BASE"')
                    }
                    if (status == 1) {
                        error('GATE: ERROR - see quality.md')
                    } else if (status != 0) {
                        error("the gate could not judge the change (exit status ${status})")
                    }
                }
            }
        }

        // The Linux binary, built on every pull request and main build, so a change that
        // breaks it fails before it is merged; Release attaches it.
        stage('Package') {
            steps {
                sh 'packaging/build-binary.sh'
            }
        }

        // A merge into main that raises the version in pyproject.toml releases it; any other
        // merge finds that release already there, so a change goes out with the next raise.
        // No check forces a pull request to raise it, as octoflow-ai's Version stage does:
        // a change to pyproject.toml holds a pull request for a human (automerge.yml), so
        // that would hold every code change. gh creates the tag v<version> on GitHub at the
        // commit built, so Jenkins needs no git push credentials.
        stage('Release') {
            when { branch 'main' }
            steps {
                withCredentials([string(credentialsId: 'GitHub-Agents', variable: 'GH_TOKEN')]) {
                    sh '''
                        # Install sets it, so a restart from this stage, which skips Install, has none and must not release "v".
                        : "${PROJECT_VERSION:?is unset; run the whole build, not a restart from the Release stage}"
                        tag="v$PROJECT_VERSION"
                        if gh release view "$tag" >/dev/null 2>gh-release-view.err; then
                            echo "$tag is already released"
                            exit 0
                        fi
                        # Anything but a missing release, e.g. a bad token, must fail rather than release twice.
                        if ! grep -q 'release not found' gh-release-view.err; then
                            cat gh-release-view.err >&2
                            exit 1
                        fi
                        gh release create "$tag" \
                            dist/hyprmuse-linux-x86_64 dist/hyprmuse-linux-x86_64.sha256 \
                            --target "$(git rev-parse HEAD)" --title "$tag" --generate-notes
                    '''
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'quality.md', allowEmptyArchive: true
            cleanWs()
        }
    }
}
