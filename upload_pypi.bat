@echo off
REM TransCoder PyPI Upload Script (Windows)
REM Usage: upload_pypi.bat [--test]

echo ==================================
echo TransCoder PyPI Upload Script
echo ==================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is required but not installed.
    exit /b 1
)

REM Install build tools
echo Installing build tools...
python -m pip install --upgrade pip build twine

REM Clean previous builds
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.egg-info rmdir /s /q *.egg-info

REM Build the package
echo Building package...
python -m build

REM Check the package
echo Checking package...
python -m twine check dist/*

REM Upload to PyPI
if "%1"=="--test" (
    echo Uploading to Test PyPI...
    python -m twine upload --repository testpypi dist/*
    echo.
    echo Package uploaded to Test PyPI!
    echo Install with: pip install --index-url https://test.pypi.org/simple/ transcoder-llm
) else (
    echo Uploading to PyPI...
    python -m twine upload dist/*
    echo.
    echo Package uploaded to PyPI!
    echo Install with: pip install transcoder-llm
)

echo.
echo ==================================
echo Upload completed successfully!
echo ==================================

pause