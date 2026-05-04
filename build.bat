@echo off
chcp 65001 > nul
echo ========================================================
echo 一键无忧 7.0 (Portable Python Env) - 打包脚本
echo ========================================================

echo.
echo [1/4] 清理旧文件...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" del /q *.spec

echo [2/4] 检查必要文件...
if not exist "uv.exe" (
    echo 错误: 未找到 uv.exe
    echo 请先运行: python download_uv.py
    pause
    exit /b 1
)

if not exist "icon.ico" (
    echo 错误: 未找到 icon.ico
    echo 请先运行: python create_icon.py
    pause
    exit /b 1
)

echo 所有文件就绪
echo.
echo [3/4] 开始打包 (文件名: portable-python-env-v7.0.3-win-x64)...
echo.

REM 自动检测系统 Python 的 Tcl/Tk 并打包进 exe（确保 tkinter 在 exe 中可用）
for /f "delims=" %%a in ('.\exe_env\Scripts\python -c "import sys,os; print(os.path.join(os.path.dirname(sys._base_executable),'tcl'))"') do set "TCL_ROOT=%%a"
echo Tcl 根目录: %TCL_ROOT%

.\exe_env\Scripts\pyinstaller ^
    --name="portable-python-env-v7.0.3-win-x64" ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="uv.exe;." ^
    --add-data="%TCL_ROOT%\tcl8.6;tcl\tcl8.6" ^
    --add-data="%TCL_ROOT%\tk8.6;tcl\tk8.6" ^
    --add-data="%TCL_ROOT%\..\DLLs\tcl86t.dll;." ^
    --add-data="%TCL_ROOT%\..\DLLs\tk86t.dll;." ^
    --hidden-import=PIL._tkinter_finder ^
    main.py

if errorlevel 1 (
    echo.
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo [4/4] 打包完成！
echo.
echo 生成文件: dist\portable-python-env-v7.0.3-win-x64.exe
dir "dist\portable-python-env-v7.0.3-win-x64.exe" | findstr "portable"

echo.
echo ========================================
echo 打包成功！
echo ========================================
pause
