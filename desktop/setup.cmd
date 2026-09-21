@echo off
cd /d "%~dp0"
python -m pip install --target "%~dp0.vendor" imageio-ffmpeg==0.6.0
if errorlevel 1 pause
