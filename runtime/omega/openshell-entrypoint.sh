#!/bin/sh
set -eu

# Shared non-root OpenShell entrypoint for StickerBook OmegaLLM. Credential-like
# values below are OpenShell placeholders, never the real provider secrets.
: "${OPENROUTER_API_KEY:?OpenShell OpenRouter placeholder missing}"

cd /PeTTa

exec env -i \
  HOME="${HOME:-/nonexistent}" \
  USER="${USER:-nobody}" \
  PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}" \
  HOSTNAME="${HOSTNAME:-}" \
  TERM="${TERM:-xterm}" \
  LANG="${LANG:-C.UTF-8}" \
  LC_ALL="${LC_ALL:-}" \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  HF_HOME="${HF_HOME:-/opt/huggingface}" \
  SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/opt/sentence_transformers}" \
  HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}" \
  TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}" \
  CHROMA_DB_PATH="${CHROMA_DB_PATH:-/PeTTa/chroma_db}" \
  EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-Local}" \
  OMEGA_DIR="${OMEGA_DIR:-/PeTTa/repos/Omega}" \
  MEMORY_DIR="${MEMORY_DIR:-/PeTTa/repos/Omega/memory}" \
  OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
  ASI_API_KEY="${ASI_API_KEY:-}" \
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  ASIONE_API_KEY="${ASIONE_API_KEY:-}" \
  sh run.sh run.metta GATEWAY_URL=http://localhost:8080 "$@"
