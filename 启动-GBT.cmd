@echo off
setlocal enableextensions
cd /d "%~dp0"
echo ==========================================
echo  GBT V8 launcher (on-demand weights)
echo ==========================================

call :probe 8791
if "%UP%"=="1" goto br_up
echo [1/3] starting bridge on :8791 ...
set GBT_ENABLE_SELFHOST_LANE=1
set GBT_OURS_BASE_URL=http://127.0.0.1:8792/v1
set GBT_SELFHOST_IDLE=900
start "" /min py -3.14 -X utf8 "tools\model-bridge\server.py" --port 8791
call :wait 8791 30
goto br_done
:br_up
echo [1/3] bridge :8791 already up (weights stay cold until first message)
:br_done

echo [2/3] doctor ...
"C:\Python312\python.exe" "tools\model-bridge\doctor.py"
echo.

if "%~1"=="--no-shell" goto no_shell
echo [3/3] starting desktop shell ...
pushd holo_pet_w3
start "" ".\node_modules\.bin\electron.cmd" .
popd
goto end
:no_shell
echo [3/3] shell skipped (--no-shell)
:end
echo.
echo done. weights load on the FIRST chat message, then idle-exit after 900s.
echo override idle window: set GBT_SELFHOST_IDLE=1800
exit /b 0

:probe
set UP=0
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1:%~1/health --max-time 3 2^>nul') do if "%%c"=="200" set UP=1
exit /b 0

:wait
set /a _n=0
:waitloop
call :probe %~1
if "%UP%"=="1" exit /b 0
set /a _n+=1
if %_n% geq %~2 exit /b 1
timeout /t 2 >nul
goto waitloop
