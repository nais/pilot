#!/bin/bash
arm=$1; n=$2; agent=$3
NODE=/Users/hans/.local/share/mise/installs/node/20.20.2/bin/node
LOADER=/Users/hans/.local/share/mise/installs/node/20.20.2/lib/node_modules/@github/copilot/npm-loader.js
TOK=$(cat /tmp/rb/.tok)
rm -rf /tmp/rb/$arm/work/gr && mkdir -p /tmp/rb/$arm/work/gr
cp /tmp/rb/goreview/audit.go /tmp/rb/goreview/audit_test.go /tmp/rb/$arm/work/gr/
cd /tmp/rb/$arm/work/gr || exit 1
if [ -n "$agent" ]; then A=(--agent "$agent"); else A=(); fi
HOME=/tmp/rb/$arm GITHUB_TOKEN="$TOK" "$NODE" "$LOADER" -p "$(cat /tmp/rb/goreview/task-goreview.txt)" --model gpt-5.6-sol --no-color --allow-all-tools "${A[@]}" > /tmp/rb/gr-$arm-$n.txt 2>&1
