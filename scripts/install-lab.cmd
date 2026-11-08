@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0.." || exit /b 1
for %%F in (requirements.txt lab\ui.py ui\index.html) do if not exist "%%F" goto incomplete_bundle

set "LAB_PY=.venv\Scripts\python.exe"
set "CHECK_PY=import struct, sys; sys.exit(0 if sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8 else 1)"
if exist "%LAB_PY%" goto check_environment

py -3.11 -I -c "%CHECK_PY%" >nul 2>&1
if not errorlevel 1 (
    py -3.11 -m venv .venv || goto install_error
    goto check_environment
)
python -I -c "%CHECK_PY%" >nul 2>&1
if errorlevel 1 (
    echo Install 64-bit Python 3.11 from https://www.python.org/downloads/windows/ and run this file again. 1>&2
    goto fail
)
python -m venv .venv || goto install_error

:check_environment
"%LAB_PY%" -I -c "%CHECK_PY%" >nul 2>&1
if errorlevel 1 (
    echo The .venv folder needs a working 64-bit Python 3.11. Rename .venv and run this file again. 1>&2
    goto fail
)
"%LAB_PY%" -I -c "from importlib.metadata import version; from pathlib import Path; pins = dict(line.split('==', 1) for line in Path('requirements.txt').read_text(encoding='utf-8-sig').splitlines() if line.strip() and not line.startswith('#')); raise SystemExit(any(version(name) != pin + ('+cpu' if name == 'torch' else '') for name, pin in pins.items()))" >nul 2>&1
if not errorlevel 1 goto launch

echo Installing the pinned CPU dependencies into .venv...
"%LAB_PY%" -I -m pip --version >nul 2>&1
if errorlevel 1 (
    "%LAB_PY%" -I -m ensurepip --upgrade || goto install_error
)
"%LAB_PY%" -I -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.10.0+cpu" || goto install_error
"%LAB_PY%" -I -m pip install -r requirements.txt || goto install_error
"%LAB_PY%" -I -m pip check || goto install_error

:launch
"%LAB_PY%" -X utf8 -m lab.ui --open || goto fail
popd
exit /b 0

:install_error
echo Setup could not finish. Check the error above and your internet connection, then run this file again. 1>&2
goto fail

:incomplete_bundle
echo Extract the entire lab ZIP before running this file. 1>&2

:fail
popd
set /p "LAB_CLOSE=Press Enter to close. "
exit /b 1
