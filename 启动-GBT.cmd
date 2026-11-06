@echo off
setlocal enableextensions
cd /d "%~dp0"
echo ==========================================
echo  GBT V8 launcher (on-demand weights)
echo ==========================================

call :probe 8791
if "%UP%"=="1" goto br_up
echo [1/5] starting bridge on :8791 ...
set GBT_ENABLE_SELFHOST_LANE=1
REM 8792 是 bridge 里 selfhost 车道名；引擎真身地址见 gbt_allinone/weights.py（当前 8111）
set GBT_OURS_BASE_URL=http://127.0.0.1:8792/v1
set GBT_SELFHOST_IDLE=900
start "" /min "%~dp0pyembed\python.exe" -X utf8 "tools\model-bridge\server.py" --port 8791
call :wait 8791 30
goto br_done
:br_up
echo [1/5] bridge :8791 already up (weights stay cold until first message)
:br_done

echo [2/5] ensuring cognitive console :8766 ...
call :probe2 8766
if "%UP2%"=="1" goto cs_up
start "" /min "pyembed\python.exe" -X utf8 "tools\console-server.py" --port 8766
call :wait2 8766 20
:cs_up
if "%UP2%"=="1" echo   cognitive console ready: http://127.0.0.1:8766/console/index.html
if "%UP2%"=="0" echo   cognitive console not ready (shell still starts)

REM ==== omni-plug gateway :7788 (2026-11-06 主人令：必须跟 APP 同步启，不许手起) ====
echo [3/5] ensuring omni-plug gateway :7788 ...
set "YBK_HOME=%~dp0..\超级万能插"
call :probe3 7788
if "%UP3%"=="1" goto ybk_up
if not exist "%YBK_HOME%\runtime\server.mjs" (
  echo   [skip] omni-plug not found: %YBK_HOME%\runtime\server.mjs
  goto ybk_done
)
where node >nul 2>nul
if errorlevel 1 (
  echo   [skip] node not in PATH -- omni-plug gateway needs node
  goto ybk_done
)
start "" /min /d "%YBK_HOME%\runtime" node server.mjs --http 7788
call :wait3 7788 15
goto ybk_done
:ybk_up
echo   omni-plug gateway :7788 already up
:ybk_done
if "%UP3%"=="1" echo   omni-plug ready: http://127.0.0.1:7788/health
if "%UP3%"=="0" echo   omni-plug not ready (GBT still works without it)

echo [4/5] doctor ...
"%~dp0pyembed\python.exe" "tools\model-bridge\doctor.py"
echo.

if "%~1"=="--no-shell" goto no_shell
echo [5/5] starting desktop shell ...
if not exist "holo_pet_w3\node_modules\.bin\electron.cmd" (
  echo   [skip] electron 没装：holo_pet_w3\node_modules\.bin\electron.cmd 不存在
  echo          装法：cd holo_pet_w3 ^&^& npm install
  echo          只想用网页版：浏览器打开 http://127.0.0.1:8766/console/index.html
  goto end
)
pushd holo_pet_w3
start "" ".\node_modules\.bin\electron.cmd" .
popd
goto end
:no_shell
echo [5/5] shell skipped (--no-shell)
:end
echo.
echo done. weights load on the FIRST chat message, then idle-exit after 900s.
echo override idle window: set GBT_SELFHOST_IDLE=1800
exit /b 0

:probe2
set UP2=0
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1:%~1/api/state --max-time 3 2^>nul') do if "%%c"=="200" set UP2=1
exit /b 0

:wait2
set /a _n2=0
:waitloop2
call :probe2 %~1
if "%UP2%"=="1" exit /b 0
set /a _n2+=1
if %_n2% geq %~2 exit /b 1
timeout /t 2 >nul
goto waitloop2

:probe3
set UP3=0
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1:%~1/health --max-time 3 2^>nul') do if "%%c"=="200" set UP3=1
exit /b 0

:wait3
set /a _n3=0
:waitloop3
call :probe3 %~1
if "%UP3%"=="1" exit /b 0
set /a _n3+=1
if %_n3% geq %~2 exit /b 1
timeout /t 2 >nul
goto waitloop3

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
