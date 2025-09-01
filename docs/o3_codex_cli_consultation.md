# O3 Codex CLI Consultation Results

**Date:** 2025-08-30  
**Topic:** Debugging Codex CLI configuration for 工房システム (Koubou System)  
**Issue:** Workers claiming no file system access despite `danger-full-access` mode

---

## Original Query

I need help debugging a Codex CLI configuration issue in my Japanese distributed task system (工房システム). Here's my current setup:

**Current codex-secure.sh configuration:**
```bash
#!/bin/bash
# Secure Codex CLI wrapper for workers with restricted file access
# 職人向けの制限付きファイルアクセス版

# プロジェクトルート設定
KOUBOU_HOME="$(cd "$(dirname "$0")/.."; pwd)"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.."; pwd)"
WORKSPACE_DIR="$KOUBOU_HOME/workspace"

# ワークスペースディレクトリを確認・作成
mkdir -p "$WORKSPACE_DIR/inputs" "$WORKSPACE_DIR/outputs" "$WORKSPACE_DIR/temp"

# 作業ディレクトリを設定
cd "$PROJECT_ROOT"

# Ollamaが起動しているか確認
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    OLLAMA_NUM_GPU=999 OLLAMA_GPU_LAYERS=999 ollama serve > "$KOUBOU_HOME/logs/ollama.log" 2>&1 &
    sleep 3
fi

echo "🏭 Flexible Codex CLI for 工房システム workers"
echo "📁 Project: $PROJECT_ROOT"
echo "📝 Read access: Full project access"
echo "✏️  Write access: docs/, scripts/, tests/, outputs/ (git protected)"
echo "⚠️  Critical files protected: .git/, .koubou/db/, production configs"
echo ""

# セキュアなCodex CLI実行 - フル自動実行モード (O3推奨設定)
# --approval-mode full-auto でファイル操作とシェル実行を許可
exec codex exec \
    --oss \
    --model "gpt-oss:20b" \
    --approval-mode full-auto \
    --sandbox danger-full-access \
    --yes --quiet --no-terminal \
    --cd "$PROJECT_ROOT" \
    --skip-git-repo-check \
    "$@"
```

**Problem:**
- Workers are delegated tasks via MCP Server → Codex CLI
- User reports "Codex isn't running. GPU isn't active."
- Tasks seem to complete but might not be using actual Codex CLI execution
- Using `--oss --model "gpt-oss:20b"` configuration

**Questions:**
1. Is the `--oss` flag correct for local GPU execution?
2. Should I be checking Ollama status if using `--oss`?
3. What's the correct model specification for local execution?
4. Are there better flags for ensuring GPU usage?
5. How can I verify Codex is actually using local GPU resources?

The system is running on WSL2 Linux with local GPU access. What's the proper configuration for local GPU-accelerated Codex CLI execution?

---

## O3 Response

Below is a concise checklist that resolves every doubt you raised and gives you a repeatable way to prove that Codex is really talking to an on-device GPU.

────────────────────────────────────────────────────────
1. Is --oss the right flag for local GPU execution?
────────────────────────────────────────────────────────
Yes.  
`codex … --oss` switches the CLI into "open-source provider" mode and points it at an OpenAI-compatible endpoint on `http://localhost:11434/v1` (Ollama if you haven't overridden anything). If the endpoint is down, Codex can silently fall back to the cloud; keeping `--oss` alone is therefore not enough—see the health-check advice in § 2. ([npmjs.com](https://www.npmjs.com/package/%40openai/codex/v/0.13.0))

────────────────────────────────────────────────────────
2. Should I keep the Ollama status check?
────────────────────────────────────────────────────────
Absolutely. The default `--oss` workflow does an Ollama-style "/api/tags ➜ /api/pull" handshake before it sends the first chat-completion call. If those calls 404, Codex exits—or worse, falls back to an OpenAI model and you only notice because the GPU stays idle. Your `curl localhost:11434/api/tags` guard is therefore the right first-line test. ([github.com](https://github.com/openai/codex/issues/2507?utm_source=openai))  

Tip: Instead of a fixed `sleep 3`, poll until `curl -sf http://localhost:11434/v1/models` succeeds; this avoids a race on first boot / big model pulls.

────────────────────────────────────────────────────────
3. Correct model spec for local inference
────────────────────────────────────────────────────────
• Short answer  `-m gpt-oss:20b` (what you already use).  
• Long answer   If you omit `-m`, Codex defaults to `gpt-oss:20b`; use `gpt-oss:120b` when you have enough VRAM (≈ 80 GB for FP16 or 48 GB for Q4_K_M). ([npmjs.com](https://www.npmjs.com/package/%40openai/codex/v/0.13.0), [openai.com](https://openai.com/index/introducing-gpt-oss?utm_source=openai))

────────────────────────────────────────────────────────
4. Any "better" flags for forcing GPU usage?
────────────────────────────────────────────────────────
Codex CLI itself has no GPU toggles—the backend decides. Expose your intent to Ollama instead:

```bash
# put this right before `ollama serve`
export OLLAMA_NUM_GPU=-1      # -1 = use all available GPUs
export OLLAMA_GPU_LAYERS=-1   # off-load every layer that fits
export OLLAMA_FLASH_ATTENTION=1   # optional speed-up
```

If you prefer CLI args:

```bash
ollama serve --num-gpu-layers -1
```

Setting exaggerated numbers like `999` does no harm but is not guaranteed to map to "all layers" on every Ollama build.

────────────────────────────────────────────────────────
5. How to verify Codex is really hitting your GPU
────────────────────────────────────────────────────────
Step-by-step proof:

a. Monitor the GPU in real time  
   ```bash
   watch -n1 nvidia-smi
   ```  
   You should see 5-10 GB (20B-q4) or 30 GB+ (120B-fp16) appear as soon as Codex starts a run. ([github.com](https://github.com/greenygh0st/ollama-server-docs/blob/main/README.md?utm_source=openai))

b. Confirm Ollama thinks the model is GPU-backed  
   ```bash
   ollama ps          # column "PROCESSOR" shows CPU/​GPU ratio
   ```

c. Ask Codex to show which provider it is using  
   ```bash
   RUST_LOG=codex_core=debug codex exec --oss -m gpt-oss:20b \
     "say hello" 2>&1 | grep provider
   ```  
   Expected log line: `provider="oss" base_url="http://localhost:11434/v1"`

d. If you still doubt it, enable Ollama debug logs  
   ```bash
   export OLLAMA_DEBUG=1
   tail -F $KOUBOU_HOME/logs/ollama.log
   ```  
   You'll see lines like `loading 58 layers onto GPU 0`.

────────────────────────────────────────────────────────
Sample tightened wrapper script
────────────────────────────────────────────────────────
```bash
#!/usr/bin/env bash
set -euo pipefail

KOUBOU_HOME="$(cd "$(dirname "$0")/.."; pwd)"
PROJECT_ROOT="$(cd "$KOUBOU_HOME/.."; pwd)"

export WORKSPACE_DIR="$KOUBOU_HOME/workspace"
mkdir -p "$WORKSPACE_DIR"/{inputs,outputs,temp}

# GPU-friendly Ollama defaults
export OLLAMA_NUM_GPU=-1
export OLLAMA_GPU_LAYERS=-1
export OLLAMA_FLASH_ATTENTION=1

# Launch Ollama if needed (poll until ready)
if ! curl -sf http://localhost:11434/v1/models >/dev/null; then
  echo "▶ Starting Ollama with full-GPU off-load…"
  nohup ollama serve >>"$KOUBOU_HOME/logs/ollama.log" 2>&1 &
  until curl -sf http://localhost:11434/v1/models >/dev/null; do
     sleep 1
  done
fi

echo "🏭 Codex (OSS) — GPU mode active"

exec codex exec \
  --oss \
  -m gpt-oss:20b \
  --approval-mode full-auto \
  --sandbox danger-full-access \
  --yes --quiet --no-terminal \
  --cd "$PROJECT_ROOT" \
  --skip-git-repo-check \
  "$@"
```

────────────────────────────────────────────────────────
Quick answers in one line
────────────────────────────────────────────────────────
1 ✔ `--oss` is the correct switch.  
2 ✔ Yes, keep/strengthen the Ollama health-check.  
3 ✔ `gpt-oss:20b` or `gpt-oss:120b`; omit `-m` for the 20 B default.  
4 ✔ GPU is driven by Ollama—use `OLLAMA_NUM_GPU / OLLAMA_GPU_LAYERS`.  
5 ✔ Watch `nvidia-smi`, `ollama ps`, or Codex debug logs to prove GPU usage.

With those tweaks your 工房システム workers should stop reporting "Codex isn't running / GPU isn't active," and you'll have an objective way to confirm that every Codex call is really being served by the local GPU.

---

## Implementation Status

- ✅ Applied O3 recommended script improvements
- ✅ Fixed Ollama environment variables (`OLLAMA_NUM_GPU=-1`, `OLLAMA_GPU_LAYERS=-1`)
- ✅ Improved health check with proper polling (`curl -sf http://localhost:11434/v1/models`)
- ✅ Added `OLLAMA_FLASH_ATTENTION=1` for performance
- ✅ Updated to use proper error handling (`set -euo pipefail`)
- ⏳ Testing GPU-accelerated worker operations in progress

## Verification Commands

```bash
# Monitor GPU usage
watch -n1 nvidia-smi

# Check Ollama model status
ollama ps

# Debug Codex provider
RUST_LOG=codex_core=debug codex exec --oss -m gpt-oss:20b "say hello" 2>&1 | grep provider

# Enable Ollama debug logs
export OLLAMA_DEBUG=1
tail -F .koubou/logs/ollama.log
```