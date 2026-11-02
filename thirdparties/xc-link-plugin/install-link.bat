@echo off
REM 把 xc-link-plugin 以 junction 方式链接进目标 FGUI 工程（修改本目录即同步到工程）
REM 用法: install-link.bat <FGUI工程根目录>
setlocal
set "SRC=%~dp0"
set "TARGET=%~1"
if "%TARGET%"=="" (
  echo 用法: %~nx0 ^<FGUI工程根目录^>
  exit /b 1
)
set "LINK=%TARGET%\plugins\xc-link-plugin"
if exist "%LINK%" (
  echo 已存在: %LINK% （先手动删除再重装）
  exit /b 1
)
if not exist "%TARGET%\plugins" mkdir "%TARGET%\plugins"
cmd /c mklink /J "%LINK%" "%SRC%"
if errorlevel 1 exit /b 1
echo 链接完成: %LINK% -^> %SRC%
