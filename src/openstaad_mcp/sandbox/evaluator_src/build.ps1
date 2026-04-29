# build.ps1 — Build evaluator.wasm from evaluator.js.
#
# Downloads extism-js and binaryen to %LOCALAPPDATA%\openstaad-mcp\tools
# on first run. Subsequent runs reuse the cache.
#
# Supply-chain integrity:
#   - extism-js: SHA-256 pinned below (upstream does not publish checksums).
#   - binaryen:  SHA-256 verified against the .sha256 sidecar published
#                alongside each GitHub release.
#   - evaluator.wasm: SHA-256 emitted after build so downstream processes
#                     can record / verify the artifact.

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sandboxDir = Split-Path -Parent $scriptDir
$outWasm = Join-Path $sandboxDir 'evaluator.wasm'

$toolsDir = Join-Path $env:LOCALAPPDATA 'openstaad-mcp\tools'
$null = New-Item -ItemType Directory -Force -Path $toolsDir

$extismJsExe = Join-Path $toolsDir 'extism-js.exe'
$binaryenDir = Join-Path $toolsDir 'binaryen-version_129'
$wasmMergeExe = Join-Path $binaryenDir 'bin\wasm-merge.exe'

# -- Pinned hashes --------------------------------------------------------
# extism-js v1.6.0 x86_64-windows — upstream does not publish checksums.
# Hash computed from the official release binary on 2026-04-27.
$ExtismJsSha256 = '5DCAF225B6EE343255B7F67E6C987F85D59C571436A60B640F89FB917FF65400'

# --- extism-js ---
if (-not (Test-Path $extismJsExe)) {
    Write-Host 'Downloading extism-js v1.6.0...'
    $gz = Join-Path $toolsDir 'extism-js.gz'
    Invoke-WebRequest -Uri 'https://github.com/extism/js-pdk/releases/download/v1.6.0/extism-js-x86_64-windows-v1.6.0.gz' -OutFile $gz -UseBasicParsing
    $in = [System.IO.File]::OpenRead($gz)
    $out = [System.IO.File]::Create($extismJsExe)
    $stream = New-Object System.IO.Compression.GzipStream($in, [System.IO.Compression.CompressionMode]::Decompress)
    $stream.CopyTo($out)
    $stream.Dispose(); $out.Dispose(); $in.Dispose()
    Remove-Item $gz

    # Verify SHA-256
    $actual = (Get-FileHash $extismJsExe -Algorithm SHA256).Hash
    if ($actual -ne $ExtismJsSha256) {
        Remove-Item $extismJsExe -Force
        throw "SHA-256 mismatch for extism-js.exe!`n  Expected: $ExtismJsSha256`n  Got:      $actual"
    }
    Write-Host "  extism-js.exe SHA-256 verified: $actual"
}

# --- binaryen (wasm-merge) ---
if (-not (Test-Path $wasmMergeExe)) {
    Write-Host 'Downloading binaryen v129...'
    $tgz = Join-Path $toolsDir 'binaryen.tar.gz'
    $sha256File = Join-Path $toolsDir 'binaryen.tar.gz.sha256'
    Invoke-WebRequest -Uri 'https://github.com/WebAssembly/binaryen/releases/download/version_129/binaryen-version_129-x86_64-windows.tar.gz' -OutFile $tgz -UseBasicParsing
    Invoke-WebRequest -Uri 'https://github.com/WebAssembly/binaryen/releases/download/version_129/binaryen-version_129-x86_64-windows.tar.gz.sha256' -OutFile $sha256File -UseBasicParsing

    # Verify SHA-256 against upstream sidecar
    $expectedHash = ((Get-Content $sha256File -Raw).Trim() -split '\s+')[0].ToUpper()
    $actualHash = (Get-FileHash $tgz -Algorithm SHA256).Hash
    if ($actualHash -ne $expectedHash) {
        Remove-Item $tgz, $sha256File -Force
        throw "SHA-256 mismatch for binaryen tarball!`n  Expected: $expectedHash`n  Got:      $actualHash"
    }
    Write-Host "  binaryen tarball SHA-256 verified: $actualHash"

    tar -xzf $tgz -C $toolsDir
    Remove-Item $tgz, $sha256File
}

# --- compile ---
$env:PATH = "$binaryenDir\bin;$env:PATH"
Push-Location $scriptDir
try {
    & $extismJsExe evaluator.js -i evaluator.d.ts -o $outWasm
    $size = (Get-Item $outWasm).Length
    $hash = (Get-FileHash $outWasm -Algorithm SHA256).Hash
    Write-Host ("Built {0} ({1:N0} bytes)" -f $outWasm, $size)
    Write-Host ("  evaluator.wasm SHA-256: {0}" -f $hash)

    # Write sidecar hash file for downstream verification
    $hashFile = "$outWasm.sha256"
    "$hash  evaluator.wasm" | Set-Content -Path $hashFile -NoNewline
    Write-Host ("  Hash written to {0}" -f $hashFile)
} finally {
    Pop-Location
}
