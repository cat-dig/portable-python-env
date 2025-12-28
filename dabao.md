# 一键无忧6.0 打包指南

## 📋 前置准备

确保项目目录下有以下文件：
- `main.py` - 主程序文件
- `build.spec` - PyInstaller 配置文件
- `icon.ico` - 应用图标
- `uv.exe` - 包管理工具 (必需)
- `python_embed.zip` - 内置 Python (可选，用于离线部署)

## 🚀 打包步骤

### 方法一：使用现有 Conda 环境

```bash
# 1. 退出其他环境 (如果有)
conda deactivate

# 2. 创建纯净的打包环境 (Python 3.10 兼容性最好)
conda create -n exe_build_env python=3.10 -y

# 3. 激活打包环境
conda activate exe_build_env

# 4. 安装打包依赖
pip install pyinstaller customtkinter requests pillow

# 5. 进入项目目录
cd /d D:\Desktop\exe

# 6. 执行打包
pyinstaller build.spec --clean

# 7. 完成后，可执行文件在 dist/ 目录下
```

### 方法二：使用 uv (更快)

```bash
# 1. 创建虚拟环境
uv venv .build_venv

# 2. 激活环境
.build_venv\Scripts\activate

# 3. 安装依赖
uv pip install pyinstaller customtkinter requests pillow

# 4. 打包
pyinstaller build.spec --clean
```

## ⚠️ 常见问题

### 1. Tcl/Tk 版本冲突
如果出现 `can't find package Tcl` 错误，请确保：
- 使用纯净的 Python 环境 (不要混用 Conda 和系统 Python)
- `build.spec` 中正确配置了 Tcl/Tk 路径

### 2. DLL 找不到
确保打包时包含了所有必要的 DLL，检查 `build.spec` 中的 `binaries` 配置。

### 3. 程序启动闪退
添加 `console=True` 到 `build.spec` 的 EXE 配置中，查看错误信息。

## 🧹 清理

```bash
# 删除打包缓存
rmdir /s /q build
rmdir /s /q dist
rmdir /s /q __pycache__

# 删除临时环境
conda deactivate
conda env remove -n exe_build_env
```

## 📁 输出

打包完成后，`dist/一键无忧6.0.exe` 即为最终可执行文件。
