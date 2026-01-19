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
echo [3/4] 开始打包 (文件名: portable-python-env-v7.0.0-win-x64)...
echo.

REM 设置 TCL/TK 环境变量
REM 注意: 即使在 main.py 中已处理，这里保持为空或注释，以免干扰 pyinstaller 分析
REM set TCL_LIBRARY=...

.\exe_env\Scripts\pyinstaller ^
    --name="portable-python-env-v7.0.0-win-x64" ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="uv.exe;." ^
    --add-data=".\env_tools\python\tcl\tcl8.6;tcl\tcl8.6" ^
    --add-data=".\env_tools\python\tcl\tk8.6;tcl\tk8.6" ^
    --add-data=".\env_tools\python\DLLs\tcl86t.dll;." ^
    --add-data=".\env_tools\python\DLLs\tk86t.dll;." ^
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
echo 生成文件: dist\portable-python-env-v7.0.0-win-x64.exe
dir "dist\portable-python-env-v7.0.0-win-x64.exe" | findstr "portable"

echo.
echo ========================================
echo 打包成功！
echo ========================================
pause
