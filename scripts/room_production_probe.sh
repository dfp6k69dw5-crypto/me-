#!/usr/bin/env bash
set -uo pipefail

git config user.name "the-room-production-probe"
git config user.email "actions@users.noreply.github.com"
ROOM_NODE_TIMEOUT_SECONDS=45
ROOM_NODE_KILL_GRACE_SECONDS=5
ROOM_RELAY_CONNECT_TIMEOUT_SECONDS=3
ROOM_RELAY_MAX_TIME_SECONDS=8
stage="startup"
model_pid=""
relay_token=""
export ROOM_MODEL_URL=""
export ROOM_CYCLE_KEY="production-probe:${GITHUB_RUN_ID}:${GITHUB_RUN_ATTEMPT}:1"

publish_failure() {
  code="$1"
  rm -rf room_parts room_work
  mkdir -p room
  python3 - "$stage" "$code" "$GITHUB_RUN_ID" <<'PY' > room/production-probe.json
import json, sys
from datetime import datetime, timezone
stage, code, run_id = sys.argv[1:]
print(json.dumps({
    "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "result": "failure",
    "stage": stage,
    "exit_code": int(code),
    "run_id": run_id,
}, indent=2))
PY
  git add room/production-probe.json
  git commit -m "Record production-equivalent Room probe failure" || true
  for attempt in 1 2 3 4; do
    if git push origin HEAD:main; then break; fi
    git fetch origin main --depth=40 || { sleep 2; continue; }
    git rebase origin/main || { git rebase --abort || true; break; }
  done
  [ -n "$model_pid" ] && kill "$model_pid" 2>/dev/null || true
  exit 1
}

refresh_relay_token() {
  token_json=$(curl -fsS --connect-timeout "$ROOM_RELAY_CONNECT_TIMEOUT_SECONDS" --max-time "$ROOM_RELAY_MAX_TIME_SECONDS" -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=room-live-mirror") || return 1
  relay_token=$(printf '%s' "$token_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("value", ""))')
  [ -n "$relay_token" ]
}
fetch_allen_turns() {
  printf '%s\n' '{"messages":[]}' > room_work/allen-inbox.json
  refresh_relay_token || return 0
  curl -fsS --connect-timeout "$ROOM_RELAY_CONNECT_TIMEOUT_SECONDS" --max-time "$ROOM_RELAY_MAX_TIME_SECONDS" -H "Authorization: Bearer ${relay_token}" "${ROOM_RELAY_URL%/}/api/participant/pending" > room_work/allen-inbox.json || printf '%s\n' '{"messages":[]}' > room_work/allen-inbox.json
}
ack_allen_turns() {
  [ -s room_work/allen-ack.json ] || return 0
  ack_count=$(python3 -c 'import json; print(len(json.load(open("room_work/allen-ack.json")).get("ids", [])))' 2>/dev/null || echo 0)
  [ "$ack_count" -gt 0 ] || return 0
  refresh_relay_token || return 0
  curl -fsS --connect-timeout "$ROOM_RELAY_CONNECT_TIMEOUT_SECONDS" --max-time "$ROOM_RELAY_MAX_TIME_SECONDS" -X POST -H "Authorization: Bearer ${relay_token}" -H "Content-Type: application/json" --data-binary @room_work/allen-ack.json "${ROOM_RELAY_URL%/}/api/participant/ack" >/dev/null || true
}
publish_relay() {
  refresh_relay_token || return 0
  curl -fsS --connect-timeout "$ROOM_RELAY_CONNECT_TIMEOUT_SECONDS" --max-time "$ROOM_RELAY_MAX_TIME_SECONDS" -X POST -H "Authorization: Bearer ${relay_token}" -H "Content-Type: application/json" --data-binary @room/feed.json "${ROOM_RELAY_URL%/}/api/ingest" >/dev/null || true
}
wait_batch() {
  failed=0
  for pid in "$@"; do wait "$pid" || failed=1; done
  [ "$failed" -eq 0 ]
}

stage="model-download"
mkdir -p .room_model/runtime
gh release download society-brain-v1 --repo "$GITHUB_REPOSITORY" --pattern 'society-brain-q4_0.gguf' --dir .room_model || publish_failure $?
gh release download society-brain-v1 --repo "$GITHUB_REPOSITORY" --pattern 'llama-runtime-linux-x64.tar.gz' --dir .room_model || publish_failure $?
echo '7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed  .room_model/society-brain-q4_0.gguf' | sha256sum -c - || publish_failure $?
echo '360a5bfab5b8fe562c52e060a998a052f5fc7d98a0448b035c2eedbb6acfbd94  .room_model/llama-runtime-linux-x64.tar.gz' | sha256sum -c - || publish_failure $?
tar -xzf .room_model/llama-runtime-linux-x64.tar.gz -C .room_model/runtime || publish_failure $?

stage="model-start"
server_bin=$(find .room_model/runtime -type f -name 'llama-server' | head -1)
[ -n "$server_bin" ] || publish_failure 127
chmod +x "$server_bin"
env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION -u ROOM_NODE_PROMPT \
  "$server_bin" -m .room_model/society-brain-q4_0.gguf --host 127.0.0.1 --port 18080 -c 16384 -np 2 >.room_model/server.log 2>&1 &
model_pid=$!
for attempt in $(seq 1 120); do
  if curl -fsS --connect-timeout 1 --max-time 2 http://127.0.0.1:18080/health >/dev/null 2>&1; then
    export ROOM_MODEL_URL='http://127.0.0.1:18080/completion'
    break
  fi
  if ! kill -0 "$model_pid" 2>/dev/null; then break; fi
  sleep 1
done
[ -n "$ROOM_MODEL_URL" ] || publish_failure 125

rm -rf room_parts room_work
mkdir -p room_parts room_work
stage="participant-fetch"
fetch_allen_turns
stage="participant-apply"
timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" python3 scripts/room_participant.py room_work/allen-inbox.json room_work/allen-ack.json || publish_failure $?

stage="sense-unprompted"
pids=()
for n in 1 2 4 5 7 8 10 11; do
  (timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION ROOM_NODE_PROMPT="" ROOM_NODE_ID="$n" python3 scripts/room_engine_v5.py node --phase sense) &
  pids+=("$!")
done
wait_batch "${pids[@]}" || publish_failure 1

for pair in "0 3" "6 9"; do
  stage="sense-prompted-${pair// /-}"
  pids=()
  for n in $pair; do
    (timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION ROOM_NODE_PROMPT="${ROOM_PROMPT_PERCEPTION:-}" ROOM_NODE_ID="$n" python3 scripts/room_skill_exec.py scripts/room_engine_v5.py node --phase sense) &
    pids+=("$!")
  done
  wait_batch "${pids[@]}" || publish_failure 1
done

stage="sense-bus"
timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION python3 scripts/room_engine_v5.py bus || publish_failure $?

stage="recurrent-unprompted"
pids=()
for n in 0 3 6 9; do
  (timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION ROOM_NODE_PROMPT="" ROOM_NODE_ID="$n" python3 scripts/room_engine_v5.py node --phase recurrent --bus room_work/bus-sense.json) &
  pids+=("$!")
done
wait_batch "${pids[@]}" || publish_failure 1

for pair in "1 4" "7 10"; do
  stage="recurrent-prompted-${pair// /-}"
  pids=()
  for n in $pair; do
    (timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION ROOM_NODE_PROMPT="${ROOM_PROMPT_DELIBERATION:-}" ROOM_NODE_ID="$n" python3 scripts/room_skill_exec.py scripts/room_engine_v5.py node --phase recurrent --bus room_work/bus-sense.json) &
    pids+=("$!")
  done
  wait_batch "${pids[@]}" || publish_failure 1
done

stage="recurrent-bus"
timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION python3 scripts/room_engine_v5.py bus2 --bus room_work/bus-sense.json || publish_failure $?

expr_nodes=(2 5 8 11)
shift=1
for rank in 0 1 2 3; do
  idx=$(((rank + shift) % 4))
  n=${expr_nodes[$idx]}
  stage="expression-node-${n}-rank-${rank}"
  timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION ROOM_NODE_PROMPT="${ROOM_PROMPT_EXPRESSION:-}" ROOM_NODE_ID="$n" ROOM_EXPRESSION_RANK="$rank" python3 scripts/room_skill_exec.py scripts/room_engine_v5.py node --phase recurrent --bus room_work/bus-recurrent.json || publish_failure $?
done

stage="private-commit"
timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" env -u ROOM_PROMPT_PERCEPTION -u ROOM_PROMPT_DELIBERATION -u ROOM_PROMPT_EXPRESSION python3 scripts/room_private_commit.py commit || publish_failure $?
stage="build-feed"
timeout -k "${ROOM_NODE_KILL_GRACE_SECONDS}s" "${ROOM_NODE_TIMEOUT_SECONDS}s" python3 scripts/build_room_feed.py || publish_failure $?

stage="git-publish"
git add room society/live.json
git commit -m "Room cognition v5 attention-routed skills beat" || publish_failure $?
pushed=0
for attempt in 1 2 3 4; do
  if git push origin HEAD:main; then pushed=1; break; fi
  git fetch origin main --depth=40 || { sleep 2; continue; }
  if ! git rebase origin/main; then git rebase --abort || true; break; fi
done
[ "$pushed" -eq 1 ] || publish_failure 74
publish_relay
ack_allen_turns

printf '%s\n' "production-equivalent probe beat published $(date -u +%Y-%m-%dT%H:%M:%SZ) run=$GITHUB_RUN_ID" > room/production-probe-success.txt
git add room/production-probe-success.txt
git commit -m "Verify production-equivalent Room beat" || true
git push origin HEAD:main || true
kill "$model_pid" 2>/dev/null || true
