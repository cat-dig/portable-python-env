# -*- mode: python ; coding: utf-8 -*-
# 一键无忧6.0 - 专业打包配置 (根据 main.py 完整需求构建)
import sys
import os
from pathlib import Path

block_cipher = None

# ============================================================
# 自动检测 Conda 环境中的 Tcl/Tk 路径
# ============================================================
def find_tcl_tk():
    """
    找到当前 Python 环境中 Tcl/Tk 的 DLL 和库文件夹路径
    """
    import tkinter
    
    # 获取 Python 解释器所在目录
    if hasattr(sys, 'base_prefix'):
        env_path = Path(sys.base_prefix)
    else:
        env_path = Path(sys.prefix)
    
    # Conda 环境下的典型路径
    # DLLs: Library/bin/tcl86t.dll, tk86t.dll
    # Libs: Library/lib/tcl8.6/, tk8.6/
    
    conda_bin = env_path / 'Library' / 'bin'
    conda_lib = env_path / 'Library' / 'lib'
    
    # 也检查标准 Python 安装路径
    standard_dlls = env_path / 'DLLs'
    standard_tcl = env_path / 'tcl'
    
    results = {
        'tcl_dll': None,
        'tk_dll': None,
        'tcl_lib': None,
        'tk_lib': None
    }
    
    # 查找 DLL
    for dll_dir in [conda_bin, standard_dlls, env_path]:
        if not dll_dir.exists():
            continue
        for f in dll_dir.iterdir():
            if f.suffix.lower() == '.dll':
                name = f.name.lower()
                if 'tcl86' in name and not results['tcl_dll']:
                    results['tcl_dll'] = str(f)
                if 'tk86' in name and not results['tk_dll']:
                    results['tk_dll'] = str(f)
    
    # 查找库文件夹
    for lib_dir in [conda_lib, standard_tcl, env_path / 'lib']:
        if not lib_dir.exists():
            continue
        tcl_folder = lib_dir / 'tcl8.6'
        tk_folder = lib_dir / 'tk8.6'
        if tcl_folder.exists() and not results['tcl_lib']:
            results['tcl_lib'] = str(tcl_folder)
        if tk_folder.exists() and not results['tk_lib']:
            results['tk_lib'] = str(tk_folder)
    
    return results

paths = find_tcl_tk()
print("=" * 60)
print("检测到的 Tcl/Tk 路径:")
for k, v in paths.items():
    print(f"  {k}: {v}")
print("=" * 60)

# ============================================================
# 构建打包配置
# ============================================================

# 二进制文件 (DLLs)
binaries = []
if paths['tcl_dll']:
    binaries.append((paths['tcl_dll'], '.'))
if paths['tk_dll']:
    binaries.append((paths['tk_dll'], '.'))

# 数据文件 (资源文件)
datas = [
    ('icon.ico', '.'),  # 应用图标
]

# 检查并添加 uv.exe (核心工具)
if os.path.exists('uv.exe'):
    datas.append(('uv.exe', '.'))
    print("✓ 已找到 uv.exe，将会打包")
else:
    print("⚠ 警告: uv.exe 不存在，打包后可能无法正常工作！")

# 检查并添加 python_embed.zip (可选，用于离线部署 Python)
if os.path.exists('python_embed.zip'):
    datas.append(('python_embed.zip', '.'))
    print("✓ 已找到 python_embed.zip，将会打包内置 Python")
else:
    print("ℹ python_embed.zip 不存在，程序将在运行时下载 Python")

# Tcl/Tk 库文件夹 - 注意目标路径！
if paths['tcl_lib']:
    datas.append((paths['tcl_lib'], 'tcl'))
if paths['tk_lib']:
    datas.append((paths['tk_lib'], 'tk'))

print("\n将打包的二进制文件:", binaries)
print("将打包的数据文件:", datas)
print("=" * 60)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # GUI 框架
        'customtkinter',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
        # 图片处理
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL._tkinter_finder',
        # 网络请求
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        # 标准库
        'json',
        'base64',
        'io',
        'threading',
        'queue',
        'pathlib',
        'zipfile',
        'shutil',
        'subprocess',
        'uuid',
        'string',
        'ctypes',
        'datetime',
        're',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除大型科学计算库 (程序不需要这些，只是分析用户代码时可能出现)
        'matplotlib', 'numpy', 'pandas', 'scipy', 
        'notebook', 'IPython', 'jupyter', 'pytest',
        'sklearn', 'tensorflow', 'torch', 'cv2',
        # 其他不需要的
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='一键无忧6.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不使用 UPX 压缩，避免兼容性问题
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
