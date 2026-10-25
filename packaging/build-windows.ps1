$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
uv sync --frozen --group windows-build
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed' }
uv run --no-sync python -c "from dictation.windows_app import WindowsApp; WindowsApp.image('idle').save('packaging/sayward.ico',sizes=[(16,16),(32,32),(48,48),(64,64)])"
uv run --no-sync python -m PyInstaller --clean --noconfirm packaging/sayward.spec
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
$compiler = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (!$compiler) { $compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
& $compiler packaging/sayward.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
Get-FileHash dist/installer/*.exe -Algorithm SHA256
