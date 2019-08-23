#!/usr/bin/env bash
set -euo pipefail

CHANGES=""
# grab from CI
DIFF_URL="${CIRCLE_COMPARE_URL:-}"
ENVIRONMENT="${CIRCLE_TAG:-}"
NAME="${CIRCLE_PROJECT_REPONAME:-}"
PREVIOUS="unknown"
USER="${CIRCLE_USERNAME:-}"
VERSION="${CIRCLE_SHA1:-}"

# grab from CLI
while getopts 'c:d:e:n:p:u:v:' flag; do
    case "${flag}" in
        c) CHANGES="${OPTARG}"               ;;
        d) DIFF_URL="${OPTARG}"              ;;
        e) ENVIRONMENT="${OPTARG}"           ;;
        n) NAME="${OPTARG}"                  ;;
        p) PREVIOUS="${OPTARG}"              ;;
        u) USER="${OPTARG}"                  ;;
        v) VERSION="${OPTARG}"               ;;
        *) error "Unexpected option ${flag}" ;;
    esac
done

# verify set
[[ -z "${NAME}" ]] && { echo "NAME is unset"; exit 1; }
[[ -z "${PREVIOUS}" ]] && { echo "PREVIOUS is unset"; exit 1; }
[[ -z "${VERSION}" ]] && { echo "VERSION is unset"; exit 1; }
[[ -z "${SLACK_DEPLOYBOT_WEBHOOK}" ]] && { echo "SLACK_DEPLOYBOT_WEBHOOK is unset"; exit 1; }

# build slack payload
PAYLOAD=$(cat <<EOF
{
    "text": "*ACHTUNG* deploying \`${NAME}\`
EOF
)
[[ -n "${ENVIRONMENT}" ]] && PAYLOAD=$(cat <<EOF
    ${PAYLOAD} (env: ${ENVIRONMENT})
EOF
)
PAYLOAD=$(cat <<EOF
    ${PAYLOAD}",
    "attachments": [
        {
            "fields": [
EOF
)
[[ -n "${DIFF_URL}" ]] && PAYLOAD=$(cat <<EOF
                ${PAYLOAD}{"title": "Version", "value": "<${DIFF_URL}|${PREVIOUS} → ${VERSION}>", "short": true}
EOF
    ) || PAYLOAD=$(cat <<EOF
                ${PAYLOAD}{"title": "Version", "value": "${PREVIOUS} → ${VERSION}", "short": true}
EOF
)
[[ -n "${USER}" ]] && PAYLOAD=$(cat <<EOF
                ${PAYLOAD},{"title": "User", "value": "${USER}", "short": true}
EOF
)
[[ -n "${CHANGES}" ]] && PAYLOAD=$(cat <<EOF
                ${PAYLOAD},{"title": "Changelog", "value": "${CHANGES}"}
EOF
)
PAYLOAD=$(cat <<EOF
            ${PAYLOAD}]
        }
    ]
}
EOF
)

# send to slack
n=0
until [ $n -gt 3 ]; do
    curl -v -f -XPOST \
        -H 'Content-Type: application/json' \
        -d "${PAYLOAD}" \
        "${SLACK_DEPLOYBOT_WEBHOOK}" && break
    n=$((n+1))
    sleep 1
done
