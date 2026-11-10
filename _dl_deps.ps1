# 下载并解包 _deps.tar（.pylibs + vendor + third_party）
# 修正上一版的中文路径编码坑：全程用 LiteralPath + .NET API，不依赖子进程继承编码。
$ErrorActionPreference = "Stop"
$R = "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8"
$Rel = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/download/v1.0.0"
$Tar = Join-Path $R "_deps.tar"
$Expect = "a0b76af68741b3571ff8d1e3e1d8a12ca4e6ee1277f0dc7a149b9a6c6413ffce"

if (Test-Path -LiteralPath $Tar) {
  Write-Host "already exists, skip download"
} else {
  $parts = @()
  for ($i = 1; $i -le 6; $i++) {
    $name = "_deps.tar.part$i"
    $dst = Join-Path $R $name
    if (-not (Test-Path -LiteralPath $dst)) {
      Write-Host "downloading $name ..."
      curl.exe -L --fail --silent --show-error --retry 3 --retry-delay 2 -o $dst "$Rel/$name"
      if ($LASTEXITCODE -ne 0) { Write-Host "part$i absent, stop"; Remove-Item -LiteralPath $dst -ErrorAction SilentlyContinue; break }
    } else { Write-Host "$name cached" }
    $parts += $dst
  }
  if ($parts.Count -eq 0) { throw "no parts downloaded" }
  Write-Host "merging $($parts.Count) parts ..."
  $out = [IO.File]::Create($Tar)
  try {
    foreach ($p in $parts) {
      $fs = [IO.File]::OpenRead($p)
      try { $fs.CopyTo($out) } finally { $fs.Close() }
    }
  } finally { $out.Close() }
  foreach ($p in $parts) { Remove-Item -LiteralPath $p -Force }
  Write-Host ("merged -> " + $Tar + "  " + [math]::Round((Get-Item -LiteralPath $Tar).Length/1GB,2) + " GB")
}

Write-Host "computing sha256 ..."
$h = (Get-FileHash -LiteralPath $Tar -Algorithm SHA256).Hash.ToLower()
Write-Host "sha256 = $h"
if ($h -ne $Expect) { throw "SHA256 MISMATCH expected=$Expect" }
Write-Host "SHA256 OK"

Write-Host "extracting to $R ..."
tar.exe -xf $Tar -C $R
if ($LASTEXITCODE -ne 0) { throw "tar extract failed: $LASTEXITCODE" }

foreach ($d in "_pylibs", "vendor", "third_party", "_upstream") {
  $p = Join-Path $R $d
  if (Test-Path -LiteralPath $p) {
    $n = ([System.IO.Directory]::GetFiles($p, "*", "AllDirectories")).Count
    Write-Host ("OK  " + $d + "  files=" + $n)
  } else {
    Write-Host ("MISS " + $d)
  }
}
Write-Host "done"
