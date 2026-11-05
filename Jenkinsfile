// Builds main and every pull request in a Multibranch Pipeline job and runs the quality
// gate (scripts/gate) on each, failing the build on GATE: ERROR or when the gate could not
// judge. For a pull request, Jenkins's GitHub App reports the result as the commit status
// continuous-integration/jenkins/pr-head, which auto-merge trusts only from that App, as
// does the ci-cd ruleset on main once agent-estate's init/github-rules.py has set it.
// docs/agents/README.md says how a pull request then merges; the agent-estate README,
// "Jenkins", says what the job and the agent need. Stages Version, Package and Release then
// release each merge into main that raises the version: scripts/release says what and when.
pipeline {
    // Builds run code agents wrote: only on agents that hold nothing an agent should not
    // have. Jenkins enforces that per node (Job Restrictions plugin), not this label.
    agent { label 'untrusted' }

    options {
        buildDiscarder(logRotator(numToKeepStr: '30'))
        timeout(time: 60, unit: 'MINUTES')
        // One build per branch at a time, so two builds of main cannot both find a
        // version unreleased and race to release it (stage Release).
        disableConcurrentBuilds()
    }

    environment {
        UV_NO_PROGRESS = '1'
    }

    stages {
        stage('Install') {
            steps {
                sh 'uv sync --frozen'
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
                    // The base reaches the shell as an environment variable, never as Groovy-built
                    // shell code. Package reads it too.
                    env.GATE_BASE = base
                    def status = sh(returnStatus: true, script: 'scripts/gate "$GATE_BASE"')
                    if (status == 1) {
                        error('GATE: ERROR - see quality.md')
                    } else if (status != 0) {
                        error("the gate could not judge the change (exit status ${status})")
                    }
                }
            }
        }

        // A pull request into main must raise the release version over main's, unless it
        // changes only exempt paths (scripts/release's header). After Gate, so a build that
        // fails it has reported its tests and gate first.
        stage('Version') {
            when { changeRequest target: 'main' }
            steps {
                sh 'scripts/release raised "$CHANGE_TARGET"'
            }
        }

        // The repo's own scripts/package, which writes what Release attaches to
        // dist/release/: run only when the change since Gate's base touches a released path,
        // so a change to docs alone builds nothing. A pull request that breaks the build so
        // fails before it is merged.
        stage('Package') {
            when { expression { fileExists('scripts/package') } }
            steps {
                script {
                    def touched = sh(returnStatus: true, script: 'scripts/release changed "$GATE_BASE"')
                    if (touched == 0) {
                        sh 'scripts/package'
                    } else if (touched == 1) {
                        echo 'Only exempt paths changed since the gate base: nothing to package.'
                    } else {
                        error("scripts/release changed failed (exit status ${touched})")
                    }
                }
            }
        }

        // Releases a merge into main whose version has no release yet; any other merge finds
        // its release there and does nothing (scripts/release publish). gh creates the tag
        // on GitHub, so Jenkins needs no git push credentials.
        stage('Release') {
            when { branch 'main' }
            steps {
                withCredentials([string(credentialsId: 'GitHub-Agents', variable: 'GH_TOKEN')]) {
                    sh 'scripts/release publish'
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
