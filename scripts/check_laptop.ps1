<#
.SYNOPSIS
  Prints the tool versions and GPU state this project needs, and whether the model fits on the GPU.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/check_laptop.ps1
#>
$ok = $true
function Show([string]$name, [scriptblock]$cmd) {
    try {
        $out = (& $cmd 2>&1 | Select-Object -First 1)
        Write-Host ("{0,-10} {1}" -f $name, $out)
    } catch {
        Write-Host ("{0,-10} MISSING" -f $name) -ForegroundColor Red
        $script:ok = $false
    }
}

Write-Host "== Tools =="
Show "python"  { python --version }
Show "node"    { node --version }
Show "npm"     { npm.cmd --version }
Show "git"     { git --version }
Show "ollama"  { ollama --version }

Write-Host "`n== GPU =="
Show "gpu" { nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader }

Write-Host "`n== Ollama models =="
try { ollama list } catch { Write-Host "ollama not running" -ForegroundColor Red; $ok = $false }

Write-Host "`n== Warm-up (num_ctx=8192, the setting the app uses) =="
$model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "llama3.1:8b" }
$url = if ($env:OLLAMA_URL) { $env:OLLAMA_URL } else { "http://localhost:11434" }
try {
    $body = @{ model = $model; stream = $false; options = @{ num_ctx = 8192 };
               messages = @(@{ role = "user"; content = "Say ready." }) } | ConvertTo-Json -Depth 5
    $t = Measure-Command { $r = Invoke-RestMethod -Method Post -Uri "$url/api/chat" -Body $body -ContentType "application/json" -TimeoutSec 180 }
    $tps = if ($r.eval_duration) { [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1) } else { "?" }
    Write-Host ("warm-up: {0:N1} s, {1} output tokens/s" -f $t.TotalSeconds, $tps)
} catch {
    Write-Host "warm-up failed: $($_.Exception.Message)" -ForegroundColor Red; $ok = $false
}
ollama ps
Write-Host "Expect PROCESSOR '100% GPU' and CONTEXT 8192. If you see CPU/GPU split, close GPU apps and rerun."

if ($env:OLLAMA_KEEP_ALIVE) { Write-Host "OLLAMA_KEEP_ALIVE=$env:OLLAMA_KEEP_ALIVE" }
else { Write-Host "OLLAMA_KEEP_ALIVE not set (model unloads after 5 min idle). Set it before the demo." -ForegroundColor Yellow }

if ($ok) { Write-Host "`ncheck_laptop: OK" -ForegroundColor Green; exit 0 }
Write-Host "`ncheck_laptop: something is missing (see red lines)" -ForegroundColor Red; exit 1
