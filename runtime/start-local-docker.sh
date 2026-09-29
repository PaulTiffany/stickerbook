#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
JEV_ENV_FILE=${1:?Usage: sh runtime/start-local-docker.sh /absolute/jev.env /absolute/llm.env}
LLM_ENV_FILE=${2:?Provide the separate OmegaLLM credential env file}
[ -f "$JEV_ENV_FILE" ] && [ -f "$LLM_ENV_FILE" ] || { echo "Provider env file not found" >&2; exit 1; }
for role in jev llm; do
 if [ "$role" = jev ]; then base=omega-jev:experiment; file=jev/Dockerfile.jev; port=8762; ENV_FILE=$JEV_ENV_FILE; else base=stickerbook-omega-llm:experiment; file=llm/Dockerfile.omega-llm; port=8761; ENV_FILE=$LLM_ENV_FILE; fi
 docker build -q -t "$base" -f "$file" .
 docker build -q -t "stickerbook-omega-$role:local" --build-arg "BASE_IMAGE=$base" -f runtime/Dockerfile.local .
 name="stickerbook-$role-local"
 docker network inspect "$name" >/dev/null 2>&1 || docker network create "$name"
 if docker container inspect "$name" >/dev/null 2>&1; then docker stop "$name" >/dev/null; docker rm "$name" >/dev/null; fi
 if [ "$role" = jev ]; then set -- commchannel=stickerbookrpc jevActionSet=stickerbook-rpc jevTransport=direct; else set --; fi
 docker run -d --name "$name" --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges --cpus 2 --memory 2g --pids-limit 256 --read-only --tmpfs /tmp:rw,nosuid,nodev,size=128m --tmpfs /PeTTa/chroma_db:rw,nosuid,nodev,uid=65534,gid=65534,size=128m --tmpfs /PeTTa/repos/Omega/memory:rw,nosuid,nodev,uid=65534,gid=65534,size=64m --network "$name" -p "127.0.0.1:$port:$port" --env-file "$ENV_FILE" -e PYTHONDONTWRITEBYTECODE=1 -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 "stickerbook-omega-$role:local" "$@" stickerbookRpcBind=0.0.0.0
 done
