@echo off
setlocal

start "Food Order API" cmd /k run_backend.bat
start "Food Order Frontend" cmd /k run_frontend.bat

endlocal
