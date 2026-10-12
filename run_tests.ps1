$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Python venv not found: $PSScriptRoot\.venv\Scripts\python.exe"
}
# PS5.1 下原生命令 stderr 经2>&1会变成 ErrorRecord，$ErrorActionPreference='Stop' 会直接中止脚本，
# 故不合并 stderr；pytest 退出码由末尾 exit 转发
& ".\.venv\Scripts\python.exe" -m pytest tests/ -x -q --tb=short
exit $LASTEXITCODE
