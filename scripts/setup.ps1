$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath .venv/Scripts/python.exe)) {
    uv venv --python 3.11 .venv
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar venv Python 3.11' }
}
uv pip install --python .venv/Scripts/python.exe torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyTorch CPU' }
uv pip install --python .venv/Scripts/python.exe transformers==4.57.6 psutil==7.2.2
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências' }
& .venv/Scripts/python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Testes falharam' }
