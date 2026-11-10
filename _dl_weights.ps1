# 下载 Q5_0 主道权重（4 片 4.88GB）→ 合并 → sha256 校验
$ErrorActionPreference = "Stop"
$W = "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\state\weights"
$Rel = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/download/v1.0.0"
$Gguf = Join-Path $W "gbt-v8-v82-q5_0.gguf"
$Expect = "983f19a66928aa6927a6b42ae4ab28ac0889e015788e4553303df01c0fcd262f"

New-Item -ItemType Directory -Force -Path $W | Out-Null

if (Test-Path $Gguf) {
  Write-Host "already exists, skip download"
} else {
  $parts = @()
  for ($i = 1; $i -le 9; $i++) {
    $name = "gbt-v8-v82-q5_0.gguf.part$i"
    $dst = Join-Path $W $name
    if (-not (Test-Path $dst)) {
      Write-Host "downloading $name ..."
      curl.exe -L --fail --silent --show-error --retry 3 --retry-delay 2 -o $dst "$Rel/$name"
      if ($LASTEXITCODE -ne 0) { Write-Host "part$i absent, stop"; Remove-Item $dst -ErrorAction SilentlyContinue; break }
    } else { Write-Host "$name cached" }
    $parts += $dst
  }
  if ($parts.Count -eq 0) { throw "no parts downloaded" }
  Write-Host "merging $($parts.Count) parts ..."
  $out = [IO.File]::Create($Gguf)
  try {
    foreach ($p in $parts) {
      $fs = [IO.File]::OpenRead($p)
      try { $fs.CopyTo($out) } finally { $fs.Close() }
    }
  } finally { $out.Close() }
  foreach ($p in $parts) { Remove-Item $p -Force }
  Write-Host ("merged -> " + $Gguf + "  " + [math]::Round((Get-Item $Gguf).Length/1GB,2) + " GB")
}

Write-Host "computing sha256 (this takes a while for 4.88GB) ..."
$h = (Get-FileHash -Path $Gguf -Algorithm SHA256).Hash.ToLower()
Write-Host "sha256 = $h"
if ($h -eq $Expect) { Write-Host "SHA256 OK" } else { Write-Host "SHA256 MISMATCH expected=$Expect" }
