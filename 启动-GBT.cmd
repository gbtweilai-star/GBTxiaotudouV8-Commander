@echo off
setlocal enableextensions
cd /d "%~dp0"
echo ==========================================
echo  GBT V8 launcher (self-hosted weights)
echo ==========================================

call :probe 8792
if "%UP%"=="1" goto llm_up
echo [1/4] starting model service on :8792 ...
start "" /min "C:\Python312\python.exe" "tools\model-bridge\local_llm_server.py" --model "state\weights\gbt-v8-v82-q5_0.gguf" --port 8792 --ctx 256 --threads 8
call :wait 8792 60
goto llm_done
:llm_up
echo [1/4] model service :8792 already up
:llm_done

call :probe 8791
if "%UP%"=="1" goto br_up
echo [2/4] starting bridge on :8791 ...
set GBT_ENABLE_SELFHOST_LANE=1
set GBT_OURS_BASE_URL=http://127.0.0.1:8792/v1
start "" /min py -3.14 -X utf8 "tools\model-bridge\server.py" --port 8791
call :wait 8791 30
goto br_done
:br_up
echo [2/4] bridge :8791 already up
:br_done

echo [3/4] doctor ...
"C:\Python312\python.exe" "tools\model-bridge\doctor.py"
echo.

if "%~1"=="--no-shell" goto no_shell
echo [4/4] starting desktop shell ...
pushd holo_pet_w3
start "" ".\node_modules\.bin\electron.cmd" .
popd
goto end
:no_shell
echo [4/4] shell skipped (--no-shell)
:end
echo.
echo done. model-chat page uses selfhost by default.
echo for a real round-trip check: doctor.py --chat
exit /b 0

:probe
set UP=0
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1/health --max-time 3 2^>nul') do set UP=0
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
