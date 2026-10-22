# Detects this computer's memory and graphics card and recommends the AI models.
# Windows: right-click this file > "Run with PowerShell", or in a terminal:
#    powershell -ExecutionPolicy Bypass -File detect-hardware.ps1           (prints the recommendation)
#    powershell -ExecutionPolicy Bypass -File detect-hardware.ps1 -Apply    (also writes it into .env)
param([switch]$Apply)

Set-Location $PSScriptRoot

$gpuGb = 0
$gpuName = ""
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $mb = (& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | ForEach-Object { [int]$_ } | Sort-Object | Select-Object -Last 1)
    if ($mb) { $gpuGb = [math]::Floor($mb / 1024) }
    $gpuName = (& nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
}
$ramGb = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)

$profile = "cpu"; $loaded = 1
if ($gpuGb -ge 20) {
    $profile = "nvidia"
    $why = "NVIDIA $gpuName with $gpuGb GB. Runs the strongest local models, fast."
    $chat = "gemma4:26b"; $extras = "qwen3.6:27b,deepseek-r1:32b,mistral-small3.2:24b,llama3.1:8b"
    if ($gpuGb -ge 40) { $loaded = 2 }
} elseif ($gpuGb -ge 11) {
    $profile = "nvidia"
    $why = "NVIDIA $gpuName with $gpuGb GB. Runs 8-14B models fast."
    $chat = "gemma4:12b"
    if ($gpuGb -ge 16) { $extras = "qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:14b" }
    else { $extras = "qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:8b" }
} elseif ($gpuGb -ge 6) {
    $profile = "nvidia"
    $why = "NVIDIA $gpuName with $gpuGb GB. Small models run fast; bigger ones spill into RAM and slow down."
    $chat = "gemma4:e4b"; $extras = "qwen3.5:4b,llama3.2:3b,mistral:7b,deepseek-r1:8b"
} elseif ($ramGb -ge 14) {
    $why = "No usable graphics card, $ramGb GB RAM. Models run on the CPU: works, but slowly."
    $chat = "gemma4:e4b"; $extras = "qwen3.5:4b,llama3.2:3b,mistral:7b,deepseek-r1:8b"
} else {
    $why = "No graphics card and only $ramGb GB RAM. Only the smallest model fits; expect slow answers."
    $chat = "gemma4:e2b"; $extras = ""
}

$settings = [ordered]@{
    COMPOSE_PROFILES = $profile
    OLLAMA_URL = "http://ollama:11434"
    CHAT_MODEL = $chat
    EXTRA_MODELS = $extras
    OLLAMA_MAX_LOADED_MODELS = $loaded
}

Write-Host "Detected: $why`n"
Write-Host "Recommended settings for .env:"
foreach ($k in $settings.Keys) { Write-Host "  $k=$($settings[$k])" }

if ($Apply) {
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
    $lines = Get-Content .env
    foreach ($k in $settings.Keys) {
        $line = "$k=$($settings[$k])"
        if ($lines -match "^$k=") { $lines = $lines -replace "^$k=.*", $line } else { $lines += $line }
    }
    Set-Content .env $lines
    Write-Host "`nWritten to .env. Next: docker compose up -d ; docker compose run --rm setup"
} else {
    Write-Host "`nRun again with -Apply to write these into .env."
}
