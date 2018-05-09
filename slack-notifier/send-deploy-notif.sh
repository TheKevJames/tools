#!/usr/bin/env bash
set -euo pipefail

# grab from CI
DIFF_URL="${CIRCLE_COMPARE_URL:-}"
NAME="${CIRCLE_PROJECT_REPONAME:-}"
PREVIOUS="unknown"
USER="${CIRCLE_USERNAME:-}"
VERSION="${CIRCLE_SHA1:-}"

# grab from CLI
while getopts 'd:n:p:u:v:' flag; do
  case "${flag}" in
    d) DIFF_URL="${OPTARG}"              ;;
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

# build slack payload
PAYLOAD=$(cat <<EOF
{
    "text": "*ACHTUNG* deploying \`${NAME}\`",
    "attachments": [
        {
            "fields": [
                {"title": "Old Version", "value": "${PREVIOUS}", "short": true},
                {"title": "New Version", "value": "${VERSION}", "short": true}
EOF
)
[[ ! -z "${DIFF_URL}" ]] && PAYLOAD+=$(cat <<EOF
                ,{"title": "Diff", "value": "<${DIFF_URL}|GitHub Diff URL>", "short": true}
EOF
)
[[ ! -z "${USER}" ]] && PAYLOAD+=$(cat <<EOF
                ,{"title": "User", "value": "${USER}", "short": true}
EOF
)
PAYLOAD+=$(cat <<EOF
            ]
        }
    ]
}
EOF
)

# send to slack
curl -XPOST \
     -H 'Content-Type: application/json' \
     -d "${PAYLOAD}" \
     "${SLACK_DEPLOYBOT_WEBHOOK}"
