# Python Portable Venv Generator

> 基于源代码分析的一键式 Python 虚拟环境生成工具

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows_x64_Only-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ⚠️ 关于虚拟环境复制使用的限制说明（请务必阅读）

### 仅支持 Windows x64

本工具**仅适用于 Windows x64 系统**，不支持：
- ❌ macOS
- ❌ Linux
- ❌ Windows 32位 (x86)
- ❌ Windows ARM

### 跨电脑复制的限制条件

如果你想将配置好的项目文件夹复制到另一台电脑直接使用，需要满足以下条件：

| 条件 | 说明 |
|------|------|
| ✅ 同操作系统 | 目标电脑也必须是 **Windows x64** |
| ✅ 同架构 | 必须是 64位系统 |
| ⚠️ 路径兼容 | 建议保持**相同的目录结构**（如都放在 `D:\Projects\`） |
| ⚠️ 盘符问题 | 虚拟环境中的某些路径可能是绝对路径，换盘符可能失效 |

**最佳实践**：在新电脑上重新运行本工具配置环境，而不是直接复制 `.venv` 文件夹。

---

## ✨ 核心特性

- 🚀 **一键配置** - 自动分析项目依赖，创建虚拟环境，安装所有包
- 🔍 **智能依赖解析** - 基于 [uv](https://github.com/astral-sh/uv) 的超高速依赖解析引擎
- 🎯 **基于规则的废弃 API 检测** - 识别代码中的历史 API 并添加版本约束建议
- 📦 **多 Python 版本** - 支持下载/切换 Python 3.9-3.13
- 🧹 **环境管理** - 批量扫描、清理虚拟环境
- 📓 **Jupyter 支持** - 自动处理 `.ipynb` 文件依赖

## 📸 预览

*（运行程序后的界面截图）*

## 🚀 快速开始

### 方式一：直接运行（推荐）

1. 下载 [最新 Release](../../releases) 中的可执行文件
2. 双击运行
3. 选择项目文件夹 → 点击"开始一键配置"

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/python-portable-venv-generator.git
cd python-portable-venv-generator

# 安装依赖
pip install customtkinter requests pillow

# 运行
python main.py
```

## 📋 依赖项

运行需要以下工具（首次运行时会自动部署）：

| 工具 | 说明 | 获取方式 |
|------|------|----------|
| `uv.exe` | 超快 Python 包管理器 | [下载](https://github.com/astral-sh/uv/releases) |
| `python_embed.zip` | 嵌入式 Python（可选） | [Python 官网](https://www.python.org/downloads/) |

## 🔧 功能详解

### 智能依赖分析
程序会扫描项目中的 `.py` 和 `.ipynb` 文件，自动提取 `import` 语句，生成 `requirements.txt`。

### 基于规则的废弃 API 检测
如果检测到代码使用了旧版本 API（如 `tf.contrib`、`FixedNoiseGP` 等），会根据预定义规则添加版本约束：

```python
# 检测到: from botorch.models.gp_regression import FixedNoiseGP
# 自动添加: botorch<=0.8.5
```

> 注：此功能基于预定义的规则列表，并非通用静态分析器。

### PyTorch/CUDA 支持
安装时会询问是否需要 GPU 版本，自动配置正确的安装源。

## 📁 项目结构

```
项目文件夹/
├── your_code.py          # 你的 Python 代码
├── .venv/                # 虚拟环境（自动创建）
├── requirements.txt      # 依赖列表（自动生成）
├── run.bat              # 运行脚本（自动生成）
├── activate_env.bat     # 激活环境脚本（自动生成）
└── env_tools/           # 工具目录（自动创建）
    ├── uv/
    └── python/
```

## 🛠️ 打包说明

如需自行打包为 exe：

```bash
# 创建打包环境
conda create -n build_env python=3.10 -y
conda activate build_env

# 安装依赖
pip install pyinstaller customtkinter requests pillow

# 打包
pyinstaller build.spec --clean
```

详见 [dabao.md](dabao.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[MIT License](LICENSE)

## 🙏 致谢

- [uv](https://github.com/astral-sh/uv) - 超快的 Python 包管理器
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化的 Tkinter UI 库
