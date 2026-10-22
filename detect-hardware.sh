#!/bin/sh
# Detects this computer's memory and graphics card and recommends the AI models.
# Mac / Linux:   sh detect-hardware.sh            (prints the recommendation)
#                sh detect-hardware.sh --apply    (also writes it into .env)
# Windows: use detect-hardware.ps1 instead.

cd "$(dirname "$0")"

gpu_mb=0
gpu_name=""
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | sort -n | tail -1 | tr -d ' ')
  gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
  gpu_mb=${gpu_mb:-0}
fi

os=$(uname -s)
apple_silicon=no
if [ "$os" = "Darwin" ]; then
  ram_mb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 ))
  [ "$(uname -m)" = "arm64" ] && apple_silicon=yes
else
  ram_mb=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 ))
fi
ram_gb=$(( ram_mb / 1024 ))
gpu_gb=$(( gpu_mb / 1024 ))

# --- Decide ---------------------------------------------------------------
profile=cpu
ollama_url=http://ollama:11434
loaded=1
if [ "$apple_silicon" = "yes" ]; then
  profile=""
  ollama_url=http://host.docker.internal:11434
  why="Mac with Apple Silicon, ${ram_gb} GB memory. Install Ollama from ollama.com (Docker cannot use the Mac's graphics chip)."
  if   [ "$ram_gb" -ge 48 ]; then chat=gemma4:26b; extras="qwen3.6:27b,deepseek-r1:32b,mistral-small3.2:24b,llama3.1:8b"; loaded=2
  elif [ "$ram_gb" -ge 24 ]; then chat=gemma4:12b; extras="qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:14b"
  else                            chat=gemma4:e4b; extras="qwen3.5:4b,llama3.2:3b,mistral:7b,deepseek-r1:8b"; fi
elif [ "$gpu_gb" -ge 20 ]; then
  profile=nvidia
  why="NVIDIA ${gpu_name} with ${gpu_gb} GB. Runs the strongest local models, fast."
  chat=gemma4:26b; extras="qwen3.6:27b,deepseek-r1:32b,mistral-small3.2:24b,llama3.1:8b"
  [ "$gpu_gb" -ge 40 ] && loaded=2
elif [ "$gpu_gb" -ge 11 ]; then
  profile=nvidia
  why="NVIDIA ${gpu_name} with ${gpu_gb} GB. Runs 8-14B models fast."
  chat=gemma4:12b
  if [ "$gpu_gb" -ge 16 ]; then extras="qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:14b"
  else extras="qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:8b"; fi
elif [ "$gpu_gb" -ge 6 ]; then
  profile=nvidia
  why="NVIDIA ${gpu_name} with ${gpu_gb} GB. Small models run fast; bigger ones spill into RAM and slow down."
  chat=gemma4:e4b; extras="qwen3.5:4b,llama3.2:3b,mistral:7b,deepseek-r1:8b"
elif [ "$ram_gb" -ge 14 ]; then
  why="No usable graphics card, ${ram_gb} GB RAM. Models run on the CPU: works, but slowly."
  chat=gemma4:e4b; extras="qwen3.5:4b,llama3.2:3b,mistral:7b,deepseek-r1:8b"
else
  why="No graphics card and only ${ram_gb} GB RAM. Only the smallest model fits; expect slow answers."
  chat=gemma4:e2b; extras=""
fi

echo "Detected: $why"
echo
echo "Recommended settings for .env:"
echo "  COMPOSE_PROFILES=$profile"
echo "  OLLAMA_URL=$ollama_url"
echo "  CHAT_MODEL=$chat"
echo "  EXTRA_MODELS=$extras"
echo "  OLLAMA_MAX_LOADED_MODELS=$loaded"

if [ "$1" = "--apply" ]; then
  [ -f .env ] || cp .env.example .env
  for pair in "COMPOSE_PROFILES=$profile" "OLLAMA_URL=$ollama_url" "CHAT_MODEL=$chat" "EXTRA_MODELS=$extras" "OLLAMA_MAX_LOADED_MODELS=$loaded"; do
    key=${pair%%=*}
    if grep -q "^$key=" .env; then
      # Replace the line in place; works with both GNU and BSD sed.
      sed -i.bak "s|^$key=.*|$pair|" .env && rm -f .env.bak
    else
      echo "$pair" >> .env
    fi
  done
  echo
  echo "Written to .env. Next: docker compose up -d && docker compose run --rm setup"
else
  echo
  echo "Run again with --apply to write these into .env."
fi
