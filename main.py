# main.py
# -*- coding: utf-8 -*-
# 一键无忧哈哈 - Python 环境自动配置工具

import sys
import os

# --- ⚡ 运行时修复：强制指定 Tcl/Tk 路径 (解决 PyInstaller 冲突) ---
if getattr(sys, 'frozen', False):
    # 只有在打包后的 exe 中才执行
    base_path = sys._MEIPASS
    # 强制覆盖环境变量，指向解压后的临时目录
    os.environ['TCL_LIBRARY'] = os.path.join(base_path, 'tcl')
    os.environ['TK_LIBRARY'] = os.path.join(base_path, 'tk')
    # 也可以尝试直接把这个目录加到 PATH (虽然主要靠变量)
    # os.environ['PATH'] = base_path + ';' + os.environ['PATH']

# ============ 启动画面 (在导入其他模块前显示) ============
import tkinter as tk

def show_splash():
    """显示启动画面"""
    splash = tk.Tk()
    splash.title("")
    splash.overrideredirect(True)  # 无边框
    
    # 获取屏幕尺寸并居中
    width, height = 300, 160
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    splash.geometry(f"{width}x{height}+{x}+{y}")
    
    # 设置背景和文字 - 四句话四行
    splash.configure(bg="#1a1a2e")
    tk.Label(splash, text="朋友们，", font=("Microsoft YaHei", 14, "bold"), 
             fg="#4fc3f7", bg="#1a1a2e").pack(pady=(15, 0))
    tk.Label(splash, text="什么他妈的理想啊？", font=("Microsoft YaHei", 14, "bold"), 
             fg="#4fc3f7", bg="#1a1a2e").pack()
    tk.Label(splash, text="生命是短暂的，", font=("Microsoft YaHei", 14, "bold"), 
             fg="#4fc3f7", bg="#1a1a2e").pack()
    tk.Label(splash, text="让我们干杯！", font=("Microsoft YaHei", 14, "bold"), 
             fg="#4fc3f7", bg="#1a1a2e").pack()
    
    splash.update()
    return splash

# 显示启动画面
_splash = show_splash()

# ============ 正常导入 ============
import subprocess
import json
import shutil
import zipfile
import requests
import threading
import uuid
import string
import ctypes
from pathlib import Path
from datetime import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import base64
from io import BytesIO
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0

# --- 路径配置 ---
def get_app_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

def get_bundled_resource(filename):
    """获取打包在exe内部的资源文件路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 解压临时目录
        return Path(sys._MEIPASS) / filename
    else:
        # 开发环境当前目录
        return Path(__file__).parent / filename

APP_DIR = get_app_path()
# 注意：以下路径将在 PythonEnvManager 中动态设置为项目目录下
# 这些全局变量仅作为初始占位符，实际使用时会被覆盖
TOOLS_DIR = None  # 将由项目路径决定
SETTINGS_FILE = APP_DIR / 'settings.json'  # 设置文件保留在软件目录

UV_DIR = None
PYTHON_DIR = None
UV_EXE_PATH = None
PIPREQS_WRAPPER = None


class PythonEnvManager:
    # Python 下载镜像源 (华为云速度快)
    PYTHON_MIRRORS = {
        'huawei': {'name': '华为云镜像', 'url': 'https://mirrors.huaweicloud.com/python/{version}/python-{version}-embed-amd64.zip'},
        'npmmirror': {'name': 'NPM镜像', 'url': 'https://registry.npmmirror.com/-/binary/python/{version}/python-{version}-embed-amd64.zip'},
        'official': {'name': '官方源', 'url': 'https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip'}
    }
    # 常用 Python 版本列表
    PYTHON_VERSIONS = ['3.13.1', '3.12.8', '3.11.11', '3.10.16', '3.9.21']
    
    # ========== 工程铁律 1: 智能依赖解析 ==========
    # 不手动固定版本，让 uv 自动解决依赖关系
    # 只有检测到废弃 API 时才添加版本约束
    ML_FRAMEWORK_PINNED_VERSIONS = {
        # 留空 - 让 uv 自动解析最新兼容版本
    }
    
    # ========== 工程铁律 2: 废弃 API 检测规则 ==========
    # 检测代码中使用的历史 API，自动降级到兼容版本
    DEPRECATED_API_PATTERNS = {
        'botorch': [
            {
                'pattern': r'from\s+botorch\.models\.gp_regression\s+import\s+FixedNoiseGP',
                'max_version': '0.8.5',
                'reason': 'FixedNoiseGP 已在 BoTorch≥0.9 中移除',
                # 联动依赖：botorch 0.8.5 需要特定版本的 gpytorch 和 torch
                'linked_deps': {
                    'gpytorch': '==1.10',
                    'torch': '>=1.11,<2.0',  # botorch 0.8.5 不支持 torch 2.x
                }
            },
            {
                'pattern': r'from\s+botorch\.acquisition\.analytic\s+import\s+ExpectedImprovement',
                'max_version': '0.9.5',
                'reason': 'ExpectedImprovement 路径在新版本中变更'
            },
        ],
        'tensorflow': [
            {
                'pattern': r'tf\.contrib\.',
                'max_version': '1.15.5',
                'reason': 'tf.contrib 在 TensorFlow 2.x 中已完全移除'
            },
            {
                'pattern': r'from\s+keras\.layers\s+import\s+CuDNNLSTM',
                'max_version': '2.12.0',
                'reason': 'CuDNNLSTM 已被合并到标准 LSTM 层'
            },
            {
                'pattern': r'tensorflow\.keras\.layers\.experimental\.',
                'max_version': '2.12.0',
                'reason': 'experimental 层已移至正式 API'
            },
        ],
        'torch': [
            {
                'pattern': r'torch\.utils\.data\._utils',
                'max_version': '1.13.1',
                'reason': '私有 API 在新版本中可能变更'
            },
        ],
        'sklearn': [
            {
                'pattern': r'from\s+sklearn\.cross_validation\s+import',
                'max_version': '0.19.2',
                'reason': 'sklearn.cross_validation 已移至 sklearn.model_selection'
            },
            {
                'pattern': r'from\s+sklearn\.grid_search\s+import',
                'max_version': '0.19.2',
                'reason': 'sklearn.grid_search 已移至 sklearn.model_selection'
            },
        ],
    }

    
    def __init__(self):
        self.project_path = None  # 初始为空，必须由用户选择
        self.mirrors = {
            'tsinghua': {'name': '清华大学', 'url': 'https://pypi.tuna.tsinghua.edu.cn/simple'},
            'aliyun': {'name': '阿里云', 'url': 'https://mirrors.aliyun.com/pypi/simple/'},
            'official': {'name': '官方源', 'url': 'https://pypi.org/simple'}
        }
        self.current_mirror = 'tsinghua'
        self.python_mirror = 'huawei'  # 默认使用华为云下载Python
        self.log_callback = None
        self.progress_callback = None
        self.use_system_python = False
        self.system_python_path = None
        self.downloaded_python_version = None  # 记录下载的Python版本
        
        # 工具目录属性 - 初始为 None，将在 set_project_path 中设置
        self.tools_dir = None
        self.uv_dir = None
        self.python_dir = None
        self.uv_exe_path = None
        self.pipreqs_wrapper = None
        self.python_exe_path = None
        
        self.current_proc = None
        self.stop_flag = False
        self.pause_flag = False # 新增暂停标志
        self.load_settings()

    def load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.use_system_python = data.get('use_system_python', False)
                    self.system_python_path = data.get('system_python_path', None)
                    self.downloaded_python_version = data.get('downloaded_python_version', None)
                    self.python_mirror = data.get('python_mirror', 'huawei')
                    if self.use_system_python and self.system_python_path:
                        self.python_exe_path = Path(self.system_python_path)
            except: pass
        else:
            self.use_system_python = False
            self.system_python_path = None
            self.downloaded_python_version = None
            self.python_mirror = 'huawei'
            # 只有在工具目录确定后才能设置默认路径
            if PYTHON_DIR:
                self.python_exe_path = PYTHON_DIR / 'python.exe'
            else:
                self.python_exe_path = None

    def save_settings(self):
        data = {
            'use_system_python': self.use_system_python,
            'system_python_path': str(self.system_python_path) if self.system_python_path else None,
            'downloaded_python_version': self.downloaded_python_version,
            'python_mirror': self.python_mirror
        }
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(data, f)
        except: pass

    def set_callbacks(self, log_cb, prog_cb):
        self.log_callback = log_cb
        self.progress_callback = prog_cb

    def _log(self, message, log_type="info"):
        if self.log_callback: self.log_callback(message, log_type)
        else: print(f"[{log_type}] {message}")

    def _progress(self, value):
        if self.progress_callback: self.progress_callback(value)

    def _run_cmd(self, cmd, env=None, cwd=None):
        if self.stop_flag: return -1, "", "任务已取消"
        try:
            # 确保实时输出的环境变量
            if env is None: env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            self.current_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, # 合并输出以简化处理
                text=True, encoding='utf-8', errors='ignore',
                env=env, cwd=cwd, creationflags=NO_WINDOW,
                bufsize=1 # 行缓冲
            )
            
            full_output = []
            
            # 实时读取
            while True:
                line = self.current_proc.stdout.readline()
                if not line and self.current_proc.poll() is not None:
                    break
                if line:
                    line_str = line.rstrip()
                    if line_str:
                        self._log(line_str) # 实时打印日志!
                        full_output.append(line)
            
            returncode = self.current_proc.poll()
            self.current_proc = None
            
            output_str = "".join(full_output)
            
            if self.stop_flag: return -1, output_str, "任务已强制停止"
            return returncode, output_str, "" # stderr 已合并
        except Exception as e:
            self.current_proc = None
            return -1, "", str(e)

    def stop_current_task(self):
        self.stop_flag = True
        if self.current_proc:
            try: self.current_proc.kill()
            except: pass
        self._log("正在停止任务...", "warning")

    def stop_current_task(self):
        self.stop_flag = True
        self.pause_flag = False # 停止时自动取消暂停
        if self.current_proc:
            try: self.current_proc.kill()
            except: pass
        self._log("正在停止任务...", "warning")

    def pause_task(self): self.pause_flag = True
    def resume_task(self): self.pause_flag = False
    def reset_stop_flag(self): 
        self.stop_flag = False
        self.pause_flag = False

    def check_system_python_availability(self):
        if SETTINGS_FILE.exists(): return None 
        sys_python = shutil.which('python')
        if sys_python:
            try:
                res = subprocess.run([sys_python, '--version'], capture_output=True, text=True, creationflags=NO_WINDOW)
                if res.returncode == 0: return sys_python
            except: pass
        return None

    def set_python_mode(self, use_system, path=None):
        self.use_system_python = use_system
        if use_system and path:
            self.system_python_path = path
            self.python_exe_path = Path(path)
        else:
            self.system_python_path = None
            self.python_exe_path = PYTHON_DIR / 'python.exe'
        self.save_settings()

    def set_project_path(self, path):
        """设置项目路径，并更新所有工具目录到项目目录下"""
        if os.path.isdir(path):
            self.project_path = path
            try: 
                os.chdir(path)
            except: 
                return False
            
            # 更新工具目录为项目目录下的 env_tools
            self.tools_dir = Path(path) / 'env_tools'
            self.uv_dir = self.tools_dir / 'uv'
            self.python_dir = self.tools_dir / 'python'
            self.uv_exe_path = self.uv_dir / 'uv.exe'
            self.pipreqs_wrapper = self.tools_dir / 'pipreqs.bat'
            
            # 更新 Python 可执行文件路径
            if not self.use_system_python:
                self.python_exe_path = self.python_dir / 'python.exe'
            
            # 同步更新全局变量（兼容旧代码）
            global TOOLS_DIR, UV_DIR, PYTHON_DIR, UV_EXE_PATH, PIPREQS_WRAPPER
            TOOLS_DIR = self.tools_dir
            UV_DIR = self.uv_dir
            PYTHON_DIR = self.python_dir
            UV_EXE_PATH = self.uv_exe_path
            PIPREQS_WRAPPER = self.pipreqs_wrapper
            
            return True
        return False

    def get_venv_info(self, venv_name='.venv'):
        venv_path = Path(self.project_path) / venv_name
        info = {'exists': False, 'path': '', 'version': '未知'}
        if venv_path.exists():
            info['exists'] = True
            info['path'] = str(venv_path)
            cfg = venv_path / 'pyvenv.cfg'
            if cfg.exists():
                try:
                    with open(cfg, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith('version = '):
                                info['version'] = line.split('=')[1].strip()
                except: pass
            if info['version'] == '未知':
                try:
                    py_exe = venv_path / 'Scripts' / 'python.exe'
                    if py_exe.exists():
                        res = subprocess.run([str(py_exe), '--version'], capture_output=True, text=True, creationflags=NO_WINDOW)
                        if res.returncode == 0: info['version'] = res.stdout.strip()
                except: pass
        return info

    def scan_simple_venvs(self, root_path=None):
        target_root = root_path if root_path else self.project_path
        venvs = []
        try:
            target_path = Path(target_root)
            if not target_path.exists(): return []
            
            self._log(f"正在扫描目录: {target_path}", "info")
            
            # 1. 检查根目录本身
            if self._is_venv(target_path):
                venvs.append({'name': f"{target_path.name} (当前目录)", 'path': str(target_path)})

            # 2. 显式检查可能得命名惯例 (比如 folder_env)
            potential_name = f"{target_path.name}_env"
            potential_path = target_path / potential_name
            if potential_path.exists() and self._is_venv(potential_path):
                 # 如果迭代器没扫到（比如权限问题），这里强制添加
                 pass # 下面的迭代通常会涵盖，但这里可以作为一个保底测试

            # 3. 检查所有子目录
            ignore_list = {'.git', '.idea', '.vscode', '__pycache__', 'node_modules'}
            
            count = 0
            for item in target_path.iterdir():
                try:
                    if item.is_dir() and item.name.lower() not in ignore_list:
                        # 增加日志调试，只打印前几个
                        # if count < 5: self._log(f"检查目录: {item.name}", "info")
                        count += 1
                        
                        if self._is_venv(item):
                            venvs.append({'name': item.name, 'path': str(item)})
                except Exception as e: 
                    # self._log(f"扫描出错 {item}: {e}", "warning")
                    continue
            
            self._log(f"扫描完成，找到 {len(venvs)} 个环境", "success")
        except Exception as e: 
            self._log(f"扫描致命错误: {e}", "error")
        return venvs

    def _is_venv(self, path):
        """统一的虚拟环境判定逻辑"""
        try:
            p = Path(path)
            # 1. 最标准判定：存在 pyvenv.cfg
            if (p / 'pyvenv.cfg').exists(): return True
            # 2. Windows 判定：存在 Scripts/python.exe
            if (p / 'Scripts' / 'python.exe').exists(): return True
            # 3. Unix/macOS 判定：存在 bin/python
            if (p / 'bin' / 'python').exists(): return True
            # 4. Conda 判定
            if (p / 'conda-meta').exists(): return True
            # 5. 宽松判定：存在 Lib/site-packages 且看起来像个环境
            if (p / 'Lib' / 'site-packages').exists(): return True
            return False
        except: return False

    def scan_recursive_venvs(self, root_paths):
        if isinstance(root_paths, str): root_paths = [root_paths]
        venvs = []
        ignore_dirs = {'.git', '.idea', '.vscode', '__pycache__', 'node_modules', 'windows', 'program files', 'program files (x86)', 'appdata', '$recycle.bin', 'system volume information', 'documents and settings'}
        for search_root in root_paths:
            if self.stop_flag: break
            search_path = Path(search_root)
            if not search_path.exists(): continue
            try:
                for root, dirs, files in os.walk(search_path, topdown=True):
                    if self.stop_flag: return venvs
                    
                    # 暂停逻辑
                    while self.pause_flag:
                        if self.stop_flag: return venvs
                        import time; time.sleep(0.5)

                    # 性能优化：排除大文件夹
                    dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs]
                    
                    root_p = Path(root)
                    if self._is_venv(root_p):
                        venvs.append({'name': root_p.name, 'path': str(root_p)})
                        # 找到 venv 后不再往其子目录扫描，提高效率
                        dirs[:] = []
            except Exception: continue
        return venvs

    def scan_python_files(self):
        files = []
        extensions = ['*.py', '*.pyw', '*.ipynb']
        try:
            for ext in extensions:
                for file in Path(self.project_path).rglob(ext):
                    if any(x in file.parts for x in ['.venv', 'venv', 'env', 'env_tools', '__pycache__', '.git', '.idea']): continue
                    files.append({'name': file.name, 'path': str(file.relative_to(self.project_path))})
        except: pass
        return sorted(files, key=lambda x: x['name'])

    # --- 核心修改：完全离线化工具准备 ---
    def ensure_tools_ready(self):
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 1. 检查/释放 uv.exe
        if not UV_EXE_PATH.exists():
            self._log("正在释放内置工具 uv...", "info")
            UV_DIR.mkdir(exist_ok=True)
            bundled_uv = get_bundled_resource('uv.exe')
            if bundled_uv.exists():
                try: shutil.copy(bundled_uv, UV_EXE_PATH); self._log("uv 工具释放成功", "success")
                except Exception as e: return False, f"释放 uv 失败: {e}"
            else: return False, "严重错误：未找到内置 uv.exe"

        # 2. 检查/释放 Python
        if self.use_system_python:
            if not self.python_exe_path.exists(): return False, f"系统 Python 未找到: {self.python_exe_path}"
        else:
            if not self.python_exe_path.exists():
                self._log("正在部署内置 Python 环境...", "info")
                if not self._deploy_bundled_python(): return False, "部署内置 Python 失败"

        # 3. 检查/安装 pipreqs
        if not PIPREQS_WRAPPER.exists():
            self._log("正在初始化依赖分析工具...", "info")
            ok, msg = self._install_pipreqs_offline()
            if not ok: return False, f"初始化失败: {msg}"
        return True, "工具就绪"

    def _deploy_bundled_python(self):
        """从打包资源中解压 Python，如果内置不存在则尝试下载"""
        # 优先找打包在 exe 里的资源
        bundled_zip = get_bundled_resource("python_embed.zip")
        
        if bundled_zip.exists():
            try:
                self._log("正在解压内置 Python...", "info")
                with zipfile.ZipFile(bundled_zip, 'r') as z: z.extractall(PYTHON_DIR)
                self._fix_pth_file()
                return True
            except Exception as e:
                self._log(f"解压 Python 失败: {e}", "error")
                return False
        else:
            # 内置不存在，尝试下载默认版本
            self._log("未找到内置 Python，正在从网络下载...", "warning")
            default_version = self.PYTHON_VERSIONS[0]  # 默认下载最新版本
            return self.download_python(default_version)
    
    def _fix_pth_file(self):
        """修改 ._pth 文件以允许 import site (pip需要)"""
        try:
            for f in PYTHON_DIR.iterdir():
                if f.name.endswith('._pth'):
                    c = f.read_text(encoding='utf-8').replace('#import site', 'import site')
                    f.write_text(c, encoding='utf-8')
        except: pass

    def download_python(self, version):
        """从镜像源下载指定版本的 Python"""
        if not self.project_path or not PYTHON_DIR:
            self._log("请先在主界面选择项目路径", "error")
            return False
            
        if self.stop_flag: return False
        
        # 清理旧的 Python 目录
        if PYTHON_DIR.exists():
            self._log("正在清理旧版本...", "info")
            try: shutil.rmtree(PYTHON_DIR)
            except Exception as e:
                self._log(f"清理失败: {e}", "error")
                return False
        PYTHON_DIR.mkdir(parents=True, exist_ok=True)
        
        # 构建下载 URL
        mirror_info = self.PYTHON_MIRRORS.get(self.python_mirror, self.PYTHON_MIRRORS['huawei'])
        url = mirror_info['url'].format(version=version)
        zip_path = TOOLS_DIR / f'python-{version}-embed-amd64.zip'
        
        self._log(f"正在从 {mirror_info['name']} 下载 Python {version}...", "info")
        self._log(f"下载地址: {url}", "info")
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.stop_flag:
                        self._log("下载已取消", "warning")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = downloaded / total_size
                            self._progress(progress)
                            if downloaded % (chunk_size * 100) == 0:
                                mb_down = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                self._log(f"下载进度: {mb_down:.1f}/{mb_total:.1f} MB ({progress*100:.0f}%)", "info")
            
            self._log("下载完成，正在解压...", "info")
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(PYTHON_DIR)
            
            # 修复 pth 文件
            self._fix_pth_file()
            
            # 删除下载的 zip 文件
            try: zip_path.unlink()
            except: pass
            
            # 保存版本信息
            self.downloaded_python_version = version
            self.use_system_python = False
            self.python_exe_path = PYTHON_DIR / 'python.exe'
            self.save_settings()
            
            self._log(f"Python {version} 安装成功！", "success")
            return True
            
        except requests.exceptions.RequestException as e:
            self._log(f"下载失败: {e}", "error")
            # 尝试备用镜像
            if self.python_mirror != 'npmmirror':
                self._log("正在尝试备用镜像 (NPM镜像)...", "warning")
                old_mirror = self.python_mirror
                self.python_mirror = 'npmmirror'
                result = self.download_python(version)
                self.python_mirror = old_mirror
                return result
            return False
        except Exception as e:
            self._log(f"安装失败: {e}", "error")
            return False

    def get_available_python_versions(self):
        """返回可供下载的 Python 版本列表"""
        return self.PYTHON_VERSIONS
    
    def get_current_python_info(self):
        """获取当前配置的 Python 信息"""
        if self.use_system_python:
            return f"系统 Python: {self.system_python_path}"
        elif self.downloaded_python_version:
            return f"已下载: Python {self.downloaded_python_version}"
        elif self.python_exe_path and self.python_exe_path.exists():
            return "内置 Python (嵌入式)"
        else:
            return "未配置 Python"
    
    def detect_required_python_version(self):
        """从项目文件中检测所需的 Python 版本"""
        project_path = Path(self.project_path)
        detected_version = None
        source = None
        
        # 1. 检查 .python-version 文件 (pyenv 风格)
        python_version_file = project_path / '.python-version'
        if python_version_file.exists():
            try:
                content = python_version_file.read_text(encoding='utf-8').strip()
                if content:
                    detected_version = content.split('\n')[0].strip()
                    source = '.python-version'
            except: pass
        
        # 2. 检查 pyproject.toml
        if not detected_version:
            pyproject = project_path / 'pyproject.toml'
            if pyproject.exists():
                try:
                    content = pyproject.read_text(encoding='utf-8')
                    # 匹配 requires-python = ">=3.8" 或 python = "^3.9"
                    import re
                    patterns = [
                        r'requires-python\s*=\s*["\']>=?(\d+\.\d+)',
                        r'python\s*=\s*["\'][\^~>=]*(\d+\.\d+)',
                        r'python_requires\s*=\s*["\']>=?(\d+\.\d+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, content)
                        if match:
                            detected_version = match.group(1)
                            source = 'pyproject.toml'
                            break
                except: pass
        
        # 3. 检查 setup.py
        if not detected_version:
            setup_py = project_path / 'setup.py'
            if setup_py.exists():
                try:
                    content = setup_py.read_text(encoding='utf-8')
                    import re
                    match = re.search(r'python_requires\s*=\s*["\']>=?(\d+\.\d+)', content)
                    if match:
                        detected_version = match.group(1)
                        source = 'setup.py'
                except: pass
        
        # 4. 检查 runtime.txt (Heroku 风格)
        if not detected_version:
            runtime = project_path / 'runtime.txt'
            if runtime.exists():
                try:
                    content = runtime.read_text(encoding='utf-8').strip()
                    import re
                    match = re.search(r'python-(\d+\.\d+\.\d+)', content)
                    if match:
                        detected_version = match.group(1)
                        source = 'runtime.txt'
                except: pass
        
        # 匹配到最接近的可用版本
        if detected_version:
            self._log(f"从 {source} 检测到 Python 版本要求: {detected_version}", "info")
            best_match = self._find_best_matching_version(detected_version)
            return best_match, source
        
        return None, None
    
    def _find_best_matching_version(self, required_version):
        """找到最匹配的可下载版本"""
        # 解析版本号
        parts = required_version.split('.')
        major = int(parts[0]) if len(parts) > 0 else 3
        minor = int(parts[1]) if len(parts) > 1 else 12
        
        # 在可用版本中找匹配的
        for ver in self.PYTHON_VERSIONS:
            ver_parts = ver.split('.')
            ver_major = int(ver_parts[0])
            ver_minor = int(ver_parts[1])
            
            # 找到第一个满足要求的版本
            if ver_major == major and ver_minor >= minor:
                return ver
            elif ver_major > major:
                continue
        
        # 如果没找到，返回第一个可用版本
        return self.PYTHON_VERSIONS[0] if self.PYTHON_VERSIONS else '3.12.8'
    
    def ensure_python_available(self, required_version=None):
        """确保 Python 可用，如果需要则下载"""
        # 如果使用系统 Python 且存在，直接返回
        if self.use_system_python and self.python_exe_path.exists():
            self._log(f"使用系统 Python: {self.python_exe_path}", "info")
            return True
        
        # 检查是否已有合适的 Python
        if self.python_exe_path.exists():
            # 如果没有指定版本，或者当前版本匹配，直接使用
            if not required_version:
                self._log("使用已配置的 Python", "info")
                return True
            elif self.downloaded_python_version:
                # 检查版本是否兼容
                req_parts = required_version.split('.')[:2]
                cur_parts = self.downloaded_python_version.split('.')[:2]
                if req_parts == cur_parts:
                    self._log(f"当前 Python {self.downloaded_python_version} 满足要求", "info")
                    return True
        
        # 需要下载
        version_to_download = required_version or self.PYTHON_VERSIONS[0]
        self._log(f"需要下载 Python {version_to_download}", "warning")
        return self.download_python(version_to_download)



    def _install_pipreqs_offline(self):
        """初始化依赖分析工具 (pipreqs)"""
        try:
            # 我们将使用 uv 创建一个独立的虚拟环境专门运行工具
            # 这样就不需要给用户的 Python 环境安装 pip，也不需要 get-pip.py
            tools_venv = TOOLS_DIR / 'env_tools'
            pipreqs_exe = tools_venv / 'Scripts' / 'pipreqs.exe'
            mirror = self.mirrors['tsinghua']['url']

            # 如果工具已经存在且可用，直接跳过
            if pipreqs_exe.exists():
                # 更新 wrapper 即可
                self._create_pipreqs_wrapper(pipreqs_exe)
                return True, "已就绪"

            self._log("正在构建独立分析环境 (使用 uv)...", "info")
            
            # 1. 确定用于创建工具环境的基础 Python
            # 首选系统 Python，其次是我们下载的 Python
            base_python = None
            sys_py = self.check_system_python_availability()
            if sys_py: base_python = sys_py
            elif self.python_exe_path.exists(): base_python = str(self.python_exe_path)
            
            # 2. 创建环境
            cmd_create = [str(UV_EXE_PATH), 'venv', str(tools_venv)]
            if base_python: cmd_create.extend(['--python', base_python])
            
            env = os.environ.copy(); env["UV_NO_PROGRESS"] = "1"
            ret, out, err = self._run_cmd(cmd_create, env=env)
            if ret != 0: return False, f"工具环境创建失败: {err}"

            # 3. 安装 pipreqs
            self._log("正在安装 pipreqs...", "info")
            env_python = tools_venv / 'Scripts' / 'python.exe'
            cmd_install = [
                str(UV_EXE_PATH), 'pip', 'install', 'pipreqs',
                '--python', str(env_python),
                '-i', mirror
            ]
            ret, out, err = self._run_cmd(cmd_install, env=env)
            if ret != 0: return False, f"pipreqs 安装失败: {err}"

            # 4. 创建包装器
            self._create_pipreqs_wrapper(pipreqs_exe)
            return True, "成功"
            
        except Exception as e: return False, str(e)

    def _create_pipreqs_wrapper(self, exe_path):
        with open(PIPREQS_WRAPPER, 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
            f.write(f'"{exe_path}" --encoding=utf-8 %*\n')

    def _convert_ipynb_to_py(self, ipynb_path, output_py_path):
        try:
            with open(ipynb_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with open(output_py_path, 'w', encoding='utf-8') as f:
                for cell in data.get('cells', []):
                    if cell.get('cell_type') == 'code':
                        source = cell.get('source', [])
                        if isinstance(source, str): f.write(source + '\n')
                        elif isinstance(source, list): f.write(''.join(source) + '\n')
            return True
        except: return False

    def generate_requirements(self, target_file=None, scan_mode='project'):
        # 纯正则扫描模式 - 无需 pipreqs
        if self.stop_flag: return False, "已停止", []
        
        try:
            self._log("正在扫描代码文件...", "info")
            files_to_scan = []
            if scan_mode == 'single' and target_file:
                files_to_scan.append(Path(target_file))
            else:
                extensions = ['*.py', '*.pyw', '*.ipynb']
                for ext in extensions:
                    for f in Path(self.project_path).rglob(ext):
                        if any(x in f.parts for x in ['.venv', 'venv', 'env', 'env_tools', '__pycache__', '.git', '.idea']): continue
                        files_to_scan.append(f)
            
            if not files_to_scan:
                req_path = Path(self.project_path) / 'requirements.txt'
                req_path.write_text("", encoding='utf-8')
                return True, "项目无 Python 代码文件，已跳过", []

            self._log(f"找到 {len(files_to_scan)} 个文件，正在分析导入...", "info")
            for f in files_to_scan[:3]:
                self._log(f"  📄 {f.name}", "info")
            if len(files_to_scan) > 3: self._log(f"  ...以及其他 {len(files_to_scan)-3} 个文件", "info")

            # --- 正则分析 ---
            import re
            import sys # Ensure sys is imported for builtin_modules
            builtin_modules = sys.builtin_module_names
            # 扩展标准库列表
            std_libs = {
                'os', 'sys', 're', 'json', 'time', 'datetime', 'math', 'random', 'shutil', 
                'subprocess', 'threading', 'pathlib', 'typing', 'collections', 'io', 'copy',
                'warnings', 'unittest', 'traceback', 'logging', 'platform', 'functools',
                'argparse', 'ast', 'asyncio', 'base64', 'calendar', 'configparser', 'contextlib',
                'csv', 'ctypes', 'dataclasses', 'decimal', 'difflib', 'distutils', 'email',
                'enum', 'errno', 'fnmatch', 'gc', 'getopt', 'getpass', 'glob', 'gzip', 'hashlib',
                'heapq', 'hmac', 'html', 'http', 'imaplib', 'importlib', 'inspect', 'itertools',
                'keyword', 'locale', 'mimetypes', 'multiprocessing', 'operator', 'pickle',
                'pkgutil', 'pprint', 'profile', 'pstats', 'queue', 'quopri', 'selectors',
                'shelve', 'signal', 'site', 'smtpd', 'smtplib', 'socket', 'socketserver',
                'sqlite3', 'ssl', 'stat', 'string', 'struct', 'tempfile', 'textwrap',
                'token', 'tokenize', 'trace', 'tty', 'types', 'urllib', 'uuid', 'venv',
                'weakref', 'webbrowser', 'wsgiref', 'xml', 'xmlrpc', 'zipfile', 'zlib', 'zoneinfo',
                # GUI 和其他标准库
                'tkinter', '_tkinter', 'turtle', 'idlelib', 'turtledemo',
                'curses', 'readline', 'rlcompleter', 'code', 'codeop',
                'concurrent', 'futures', 'runpy', 'sched', 'secrets', 'select',
                'pty', 'pwd', 'grp', 'crypt', 'termios', 'resource', 'syslog',
                'winreg', 'winsound', 'msvcrt', 'msilib',  # Windows 专用
                'posix', 'posixpath', 'ntpath', 'genericpath',
                'abc', 'aifc', 'binascii', 'binhex', 'bisect', 'builtins',
                'chunk', 'cmath', 'cmd', 'codecs', 'colorsys', 'compileall',
                'copyreg', 'cProfile', 'dis', 'doctest', 'filecmp', 'fileinput',
                'formatter', 'fractions', 'ftplib', 'gettext', 'graphlib',
                'imghdr', 'imp', 'ipaddress', 'lib2to3', 'linecache', 'lzma',
                'mailbox', 'mailcap', 'marshal', 'mmap', 'modulefinder', 'netrc',
                'nis', 'nntplib', 'numbers', 'optparse', 'ossaudiodev', 'parser',
                'pathlib', 'pdb', 'pipes', 'poplib', 'pyclbr', 'py_compile',
                'pydoc', 'pyexpat', 'reprlib', 'setsox', 'shlex', 'sndhdr',
                'spwd', 'statistics', 'stringprep', 'sunau', 'symbol', 'symtable',
                'sys', 'sysconfig', 'tabnanny', 'tarfile', 'telnetlib', 'test',
                'timeit', 'tomllib', 'tracemalloc', 'unicodedata', 'uu', 'wave',
                'winreg', 'winsound', 'xdrlib', 'zipapp', 'zipimport'
            }
            
            found_pkgs = set()
            pkg_map = {
                'sklearn': 'scikit-learn', 'cv2': 'opencv-python', 'PIL': 'Pillow',
                'yaml': 'PyYAML', 'bs4': 'beautifulsoup4', 'xgb': 'xgboost',
                'lgb': 'lightgbm', 'tf': 'tensorflow', 'wx': 'wxPython'
            }
            
            ignore_modules = {
                'mpl_toolkits', 'sklearn.utils', 'PIL.Image', 'matplotlib.pyplot',
                'matplotlib.font_manager', 'mpl_toolkits.mplot3d', 'cv2.cv2'
            }
            
            # 收集所有代码内容，用于废弃 API 检测
            all_code_content = ""
            
            for file_path in files_to_scan:
                if self.stop_flag: return False, "任务已停止", []
                try:
                    # For .ipynb files, convert to a temporary string content for scanning
                    content = ""
                    if file_path.suffix == '.ipynb':
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        for cell in data.get('cells', []):
                            if cell.get('cell_type') == 'code':
                                source = cell.get('source', [])
                                if isinstance(source, str): content += source + '\n'
                                elif isinstance(source, list): content += ''.join(source) + '\n'
                    else:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # 收集代码用于 API 检测
                    all_code_content += content + "\n"

                    # 1. import xxx
                    matches = re.findall(r'^\s*import\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
                    for m in matches:
                        if m not in std_libs and m not in builtin_modules and m not in ignore_modules:
                            found_pkgs.add(pkg_map.get(m, m))
                    
                    # 2. from xxx
                    matches = re.findall(r'^\s*from\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
                    for m in matches:
                        if m not in std_libs and m not in builtin_modules and m not in ignore_modules:
                            found_pkgs.add(pkg_map.get(m, m))
                    
                    # --- 智能推断隐式依赖 ---
                    if 'pandas' in found_pkgs or 'pd' in found_pkgs: # pd 可能是别名，但 map 里 pandas -> pandas
                         # 检查是否有 Excel 写入操作
                         if 'to_excel' in content or 'ExcelWriter' in content:
                             found_pkgs.add('openpyxl')
                             self._log(f"智能推断: 检测到 Excel 操作，添加 openpyxl", "info")
                    if 'matplotlib' in found_pkgs or 'plt' in found_pkgs:
                         # matplotlib 通常需要 pillow 处理图像保存
                         found_pkgs.add('Pillow')
                except Exception: # Catch any error during file reading/parsing
                    continue
            
            # --- 智能推断 Jupyter 依赖 ---
            # 如果项目包含 .ipynb 文件，自动添加 ipykernel（VSCode 运行 Notebook 必需）
            has_ipynb = any(f.suffix == '.ipynb' for f in files_to_scan)
            if has_ipynb:
                found_pkgs.add('ipykernel')
                found_pkgs.add('jupyter')
                self._log("智能推断: 检测到 Jupyter Notebook，添加 ipykernel 和 jupyter", "info")
            
            packages = sorted(list(found_pkgs))
            # 过滤掉以下划线开头的包 (通常是内部模块) 以及空字符串
            packages = [p for p in packages if p and not p.startswith('_')]
            
            # ========== 工程铁律: 版本固定与 API 检测 ==========
            version_decisions = {}  # {包名: (版本约束, 原因)}
            deprecated_warnings = []  # 废弃 API 警告列表
            
            for pkg in packages:
                pkg_lower = pkg.lower()
                
                # 铁律 2: 检测废弃 API - 使用 <= 给 uv 解析空间
                if pkg_lower in self.DEPRECATED_API_PATTERNS or pkg in self.DEPRECATED_API_PATTERNS:
                    patterns = self.DEPRECATED_API_PATTERNS.get(pkg_lower) or self.DEPRECATED_API_PATTERNS.get(pkg, [])
                    for rule in patterns:
                        if re.search(rule['pattern'], all_code_content):
                            max_ver = rule['max_version']
                            reason = rule['reason']
                            # 使用 <= 而不是 ==，让 uv 在兼容范围内自动选择最优版本
                            version_decisions[pkg] = (f"<={max_ver}", f"🔍 {reason}")
                            deprecated_warnings.append((pkg, max_ver, reason))
                            # 不再手动处理联动依赖，让 uv 自动解决
                            break
                
                # 铁律 1: ML 框架版本固定（如果没有被 API 检测覆盖）
                if pkg not in version_decisions:
                    if pkg in self.ML_FRAMEWORK_PINNED_VERSIONS:
                        version_decisions[pkg] = (
                            self.ML_FRAMEWORK_PINNED_VERSIONS[pkg], 
                            "📌 ML 框架安全版本"
                        )
                    elif pkg_lower in self.ML_FRAMEWORK_PINNED_VERSIONS:
                        version_decisions[pkg] = (
                            self.ML_FRAMEWORK_PINNED_VERSIONS[pkg_lower], 
                            "📌 ML 框架安全版本"
                        )
            
            # ========== 铁律 3: 生成解释性日志报告 ==========
            if deprecated_warnings:
                self._log("=" * 50, "warning")
                self._log("⚠️ 检测到历史/废弃 API，已自动降级版本:", "warning")
                for pkg, ver, reason in deprecated_warnings:
                    self._log(f"  • {pkg} → {ver}: {reason}", "warning")
                self._log("=" * 50, "warning")
            
            ml_pinned_count = sum(1 for p in packages if p in version_decisions and "安全版本" in version_decisions[p][1])
            if ml_pinned_count > 0:
                self._log(f"📌 已为 {ml_pinned_count} 个 ML/DL 框架固定安全版本", "info")
            
            # 生成 requirements.txt (带版本约束)
            req_path = Path(self.project_path) / 'requirements.txt'
            with open(req_path, 'w', encoding='utf-8') as f:
                for pkg in packages:
                    if pkg in version_decisions:
                        version_spec, reason = version_decisions[pkg]
                        f.write(f"{pkg}{version_spec}  # {reason}\n")
                    else:
                        f.write(f"{pkg}\n")
                
            if packages:
                self._log(f"分析完成，发现 {len(packages)} 个依赖包", "success")
                if version_decisions:
                    self._log(f"  其中 {len(version_decisions)} 个已固定版本 (工程铁律)", "success")
                return True, f"分析完成，发现 {len(packages)} 个依赖", packages
            else:
                self._log("分析完成：未发现第三方依赖包 (仅使用标准库)", "success")
                return True, "依赖已同步 (空文件)", []
                
        except Exception as e: 
            return False, f"分析失败: {str(e)}", []

    def analyze_package_compatibility(self, packages):
        """分析依赖包的 Python 版本兼容性"""
        if not packages:
            return None, "无需分析（项目仅使用标准库）"
        
        self._log(f"正在分析 {len(packages)} 个依赖包的版本兼容性...", "info")
        
        # 各版本兼容计数
        version_scores = {v: 0 for v in self.PYTHON_VERSIONS}
        problem_packages = []  # 可能有问题的包
        
        for pkg in packages:
            if self.stop_flag: return None, "已停止"
            try:
                # 查询 PyPI API
                resp = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=5)
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                info = data.get('info', {})
                requires_python = info.get('requires_python', '')
                
                if not requires_python:
                    # 没有标明兼容性，假设都兼容
                    for v in version_scores: version_scores[v] += 1
                    continue
                
                # 解析 requires_python (例如 ">=3.7", ">=3.8,<3.12")
                for ver_key in version_scores:
                    major, minor = int(ver_key.split('.')[0]), int(ver_key.split('.')[1])
                    is_compatible = self._check_python_version_compat(requires_python, major, minor)
                    if is_compatible:
                        version_scores[ver_key] += 1
                    else:
                        problem_packages.append((pkg, requires_python, ver_key))
                        
            except Exception:
                # 查询失败，假设都兼容
                for v in version_scores: version_scores[v] += 1
        
        # 找出兼容所有包的版本
        total_packages = len(packages)
        fully_compatible = [v for v, score in version_scores.items() if score == total_packages]
        
        if fully_compatible:
            # 优先推荐 3.12.x 或最新的兼容版本
            for preferred in ['3.12.8', '3.11.11', '3.10.16']:
                if preferred in fully_compatible:
                    return preferred, f"推荐版本: {preferred} (兼容所有 {total_packages} 个依赖)"
            return fully_compatible[0], f"推荐版本: {fully_compatible[0]} (兼容所有 {total_packages} 个依赖)"
        else:
            # 找兼容性最高的版本
            best_version = max(version_scores, key=version_scores.get)
            best_score = version_scores[best_version]
            return best_version, f"建议版本: {best_version} (兼容 {best_score}/{total_packages} 个依赖，部分包可能需手动处理)"

    def _check_python_version_compat(self, requires_python, major, minor):
        """检查指定的 Python 版本是否满足 requires_python 要求"""
        import re
        version_tuple = (major, minor)
        
        # 去除空格
        requires_python = requires_python.replace(' ', '')
        
        # 分割多个条件 (例如 ">=3.7,<3.12")
        conditions = re.split(r',(?![^()]*\))', requires_python)
        
        for cond in conditions:
            cond = cond.strip()
            if not cond: continue
            
            # 匹配版本号
            match = re.match(r'([><=!~]+)?(\d+)(?:\.(\d+))?(?:\.(\d+))?', cond)
            if not match: continue
            
            op = match.group(1) or '=='
            req_major = int(match.group(2))
            req_minor = int(match.group(3)) if match.group(3) else 0
            req_tuple = (req_major, req_minor)
            
            if op == '>=':
                if version_tuple < req_tuple: return False
            elif op == '>':
                if version_tuple <= req_tuple: return False
            elif op == '<=':
                if version_tuple > req_tuple: return False
            elif op == '<':
                if version_tuple >= req_tuple: return False
            elif op == '==' or op == '~=':
                if version_tuple[0] != req_tuple[0]: return False
            elif op == '!=':
                if version_tuple == req_tuple: return False
        
        return True

    def create_venv(self, version=None, venv_name='.venv'):
        if self.stop_flag: return False, "已停止"
        success, msg = self.ensure_tools_ready()
        if not success: return False, msg
        
        self._log(f"正在创建虚拟环境 ({venv_name})...", "info")
        
        # 核心修复：uv --python 参数
        # 如果我们已经下载并配置了对应的 python.exe，直接传绝对路径
        target_python = str(self.python_exe_path)
        
        # 只有当用户强制指定了不同于当前配置的版本时，才传版本号 (这可能会失败，除非系统安装了)
        # 但通常 ensure_python_available 已经确保了 self.python_exe_path 是正确的
        
        cmd = [str(UV_EXE_PATH), 'venv', venv_name, '--python', target_python]
        env = os.environ.copy(); env["UV_NO_PROGRESS"] = "1"
        
        ret, out, err = self._run_cmd(cmd, env=env)
        if ret == 0: return True, "创建成功"
        return False, err

    def install_dependencies(self, venv_name='.venv', pytorch_source=None):
        """安装项目依赖
        
        Args:
            venv_name: 虚拟环境名称
            pytorch_source: PyTorch 安装源 (None=使用默认PyPI, 否则使用指定源如 CPU/GPU)
        """
        if self.stop_flag: return False, "已停止"
        if not Path('requirements.txt').exists(): return False, "无 requirements.txt"
        venv_python = Path(venv_name) / 'Scripts' / 'python.exe'
        if not venv_python.exists(): return False, "虚拟环境异常"
        
        mirror_url = self.mirrors[self.current_mirror]['url']
        
        # 如果指定了 PyTorch 源，先单独安装 PyTorch 相关包
        if pytorch_source:
            self._log(f"正在从 PyTorch 官方源安装 PyTorch...", "info")
            torch_pkgs = ['torch', 'torchvision', 'torchaudio']
            cmd_torch = [
                str(UV_EXE_PATH), 'pip', 'install', 
                *torch_pkgs,
                '--python', str(venv_python), 
                '--index-url', pytorch_source
            ]
            ret, out, err = self._run_cmd(cmd_torch)
            if ret != 0:
                self._log(f"PyTorch 安装失败: {err[:100]}", "warning")
            else:
                self._log("PyTorch 安装成功 ✓", "success")
        
        # 安装其他依赖
        self._log(f"正在安装其他依赖 (源: {self.mirrors[self.current_mirror]['name']})...", "info")
        cmd = [str(UV_EXE_PATH), 'pip', 'install', '-r', 'requirements.txt', '--python', str(venv_python), '--index-url', mirror_url]
        
        ret, out, err = self._run_cmd(cmd)
        if ret == 0:
            # ========== 安装成功后：锁定实际版本 ==========
            self._log("正在生成版本锁定文件...", "info")
            try:
                # 使用 uv pip freeze 获取实际安装的版本
                cmd_freeze = [str(UV_EXE_PATH), 'pip', 'freeze', '--python', str(venv_python)]
                ret_freeze, freeze_out, _ = self._run_cmd(cmd_freeze)
                if ret_freeze == 0 and freeze_out.strip():
                    # 用实际版本覆盖 requirements.txt
                    req_path = Path(self.project_path) / 'requirements.txt'
                    with open(req_path, 'w', encoding='utf-8') as f:
                        f.write("# 由工具自动生成 - 实际安装版本\n")
                        f.write(f"# 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(freeze_out)
                    self._log("✅ 已锁定实际安装版本到 requirements.txt", "success")
            except Exception as e:
                self._log(f"版本锁定失败 (不影响使用): {e}", "warning")
            return True, out
        return False, err

    def create_scripts(self, target_file=None, venv_name='.venv'):
        try:
            with open('activate_env.bat', 'w', encoding='utf-8') as f:
                f.write(f'@echo off\ncd /d "%~dp0"\ncall {venv_name}\\Scripts\\activate.bat\ncmd /k\n')
            if target_file:
                target_path = Path(target_file); rel = target_path.name
                if target_path.suffix == '.ipynb':
                    with open(f'run_{target_path.stem}.bat', 'w', encoding='utf-8') as f:
                        f.write(f'@echo off\ncd /d "%~dp0"\ncall {venv_name}\\Scripts\\activate.bat\n')
                        f.write('echo 正在尝试启动 Jupyter Notebook...\n')
                        f.write('pip install jupyter notebook -q\n')
                        f.write(f'jupyter notebook "{rel}"\n')
                        f.write('pause\n')
                else:
                    with open(f'run_{target_path.stem}.bat', 'w', encoding='utf-8') as f:
                        f.write(f'@echo off\ncd /d "%~dp0"\ncall {venv_name}\\Scripts\\activate.bat\npython "{rel}" %*\npause\n')
            return True, "脚本创建成功"
        except: return False, "脚本创建失败"
        
    def delete_venv_with_progress(self, venv_path_str):
        path = Path(venv_path_str)
        if not path.is_absolute():
            path = Path(self.project_path) / venv_path_str
        if not path.exists(): return True, "不存在"
        try:
            self._log(f"正在删除 {path.name} ...", "info")
            # 1. 尝试 Python 原生删除 (shutil)
            # 先修改权限，防止因只读属性导致删除失败
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    try: os.chmod(os.path.join(root, d), 0o777)
                    except: pass
                for f in files:
                    try: os.chmod(os.path.join(root, f), 0o777)
                    except: pass
            
            shutil.rmtree(path, ignore_errors=True)
            
            # 2. 如果还在，尝试 Windows 强制删除命令
            if path.exists():
                self._log("尝试强制删除...", "warning")
                subprocess.run(['rd', '/s', '/q', str(path)], shell=True, creationflags=NO_WINDOW)
            
            if path.exists():
                return False, "删除失败，文件可能被占用"
            return True, "已删除"
        except Exception as e: return False, str(e)

    def clean_project(self, progress_callback=None):
        """彻底清理项目，删除虚拟环境和生成的文件
        
        Args:
            progress_callback: 可选的进度回调函数，接受 0-1 之间的浮点数
        """
        def _update_progress(value):
            if progress_callback:
                progress_callback(value)
        
        try:
            self._log("正在分析项目...", "info")
            _update_progress(0.05)
            
            # 智能探测要删除的虚拟环境
            venvs_to_delete = set()
            
            # 1. 添加默认目标
            for default_name in ['.venv', 'venv', 'env']:
                default_path = Path(self.project_path) / default_name
                if default_path.exists():
                    venvs_to_delete.add(str(default_path))
            
            # 2. 解析生成的 bat 文件，寻找实际使用的环境名
            for bat in Path(self.project_path).glob('run_*.bat'):
                try:
                    content = bat.read_text(encoding='utf-8', errors='ignore')
                    import re
                    m = re.search(r'call\s+"?(.+?)[\\\/]Scripts[\\\/]activate\.bat"?', content, re.IGNORECASE)
                    if m:
                        env_name = m.group(1)
                        env_path = Path(self.project_path) / env_name
                        if env_path.exists():
                            venvs_to_delete.add(str(env_path))
                except: pass
            
            # 3. 扫描项目目录下的所有虚拟环境（关键修复！）
            try:
                for item in Path(self.project_path).iterdir():
                    if item.is_dir() and self._is_venv(item):
                        venvs_to_delete.add(str(item))
            except: pass
            
            _update_progress(0.1)
            
            total_venvs = len(venvs_to_delete)
            if total_venvs:
                self._log(f"发现 {total_venvs} 个虚拟环境待清理", "info")
            
            # 执行删除 - 增强版，处理被锁定的文件
            
            # 1. 全局进程清理 (确保无占用) - 更全面的进程列表
            self._log("正在终止可能占用的进程...", "info")
            _update_progress(0.15)
            for exe in ['python.exe', 'pythonw.exe', 'pip.exe', 'pip3.exe', 'uv.exe', 'pipreqs.exe', 'cmd.exe']:
                try: 
                    subprocess.run(
                        ['taskkill', '/F', '/IM', exe], 
                        creationflags=0x08000000, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        timeout=5
                    )
                except: pass
            
            import time
            time.sleep(2)  # 延长等待时间
            _update_progress(0.2)
            
            # 2. 删除所有检测到的虚拟环境
            venv_list = list(venvs_to_delete)
            for i, vpath_str in enumerate(venv_list):
                vpath = Path(vpath_str)
                if not vpath.exists():
                    continue
                
                # 更新进度 (虚拟环境删除占 20%-70% 的进度)
                if total_venvs > 0:
                    venv_progress = 0.2 + (i / total_venvs) * 0.5
                    _update_progress(venv_progress)
                    
                self._log(f"正在删除 ({i+1}/{total_venvs}): {vpath.name}", "info")
                
                # 方法1: 修改权限后用 shutil
                try:
                    for root, dirs, files in os.walk(vpath):
                        for d in dirs:
                            try: os.chmod(os.path.join(root, d), 0o777)
                            except: pass
                        for f in files:
                            try: os.chmod(os.path.join(root, f), 0o777)
                            except: pass
                    shutil.rmtree(vpath, ignore_errors=True)
                except: pass
                
                # 方法2: 如果还存在，用 Windows rmdir
                if vpath.exists():
                    try:
                        subprocess.run(
                            ['cmd', '/c', 'rmdir', '/s', '/q', str(vpath)], 
                            shell=False, creationflags=NO_WINDOW, timeout=60,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except: pass
                
                # 方法3: 如果还存在，用 PowerShell 强制删除
                if vpath.exists():
                    try:
                        subprocess.run(
                            ['powershell', '-Command', f'Remove-Item -Path "{vpath}" -Recurse -Force -ErrorAction SilentlyContinue'], 
                            shell=False, creationflags=NO_WINDOW, timeout=60,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except: pass
                
                # 检查结果
                if vpath.exists():
                    self._log(f"警告: {vpath.name} 可能未完全删除", "warning")
                else:
                    self._log(f"已删除: {vpath.name}", "success")

            # 清理生成的文件
            _update_progress(0.75)
            self._log("正在清理生成的文件...", "info")
            for f in Path(self.project_path).glob('run_*.bat'): 
                try: f.unlink()
                except: pass
            
            for f in ['requirements.txt', 'activate_env.bat']: 
                p = Path(self.project_path)/f
                if p.exists(): 
                    try: p.unlink()
                    except: pass
            
            _update_progress(0.85)
            
            # 清理工具目录
            if SETTINGS_FILE.exists(): 
                try: SETTINGS_FILE.unlink()
                except: pass
            if TOOLS_DIR.exists():
                self._log("正在清理工具缓存...", "info")
                try:
                    shutil.rmtree(TOOLS_DIR, ignore_errors=True)
                except: pass
                if TOOLS_DIR.exists():
                    try:
                        subprocess.run(
                            ['powershell', '-Command', f'Remove-Item -Path "{TOOLS_DIR}" -Recurse -Force -ErrorAction SilentlyContinue'], 
                            shell=False, creationflags=NO_WINDOW, timeout=30,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except: pass
            
            _update_progress(1.0)
            return True, "清理完成 (生成文件及虚拟环境已删除)"
        except Exception as e: return False, f"清理失败: {str(e)}"

class PythonManagerWindow(ctk.CTkToplevel):
    """Python 版本管理窗口 - 下载和管理 Python 版本"""
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.title("Python 管理 - 下载/切换版本")
        self.geometry("550x500")
        self.manager = manager
        self.parent = parent
        self.downloading = False
        
        # 窗口置顶和模态设置
        self.transient(parent)  # 关联到父窗口
        self.grab_set()  # 模态窗口，阻止与父窗口交互
        self.lift()  # 置于最前
        self.focus_force()  # 强制获取焦点

        
        # 当前状态
        status_frame = ctk.CTkFrame(self)
        status_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(status_frame, text="当前 Python 配置", font=("bold", 14)).pack(anchor="w", pady=(5,0))
        self.status_label = ctk.CTkLabel(status_frame, text=self.manager.get_current_python_info(), 
                                          text_color="cyan", font=("Arial", 12))
        self.status_label.pack(anchor="w", pady=5)
        
        # 版本选择 - 使用单选按钮
        version_frame = ctk.CTkFrame(self)
        version_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(version_frame, text="选择 Python 版本:", font=("bold", 13)).pack(anchor="w", pady=(10,5))
        
        versions = self.manager.get_available_python_versions()
        self.version_var = tk.StringVar(value=versions[0] if versions else "3.12.8")
        
        # 创建版本选择网格
        ver_grid = ctk.CTkFrame(version_frame, fg_color="transparent")
        ver_grid.pack(fill="x", pady=5)
        
        # 版本说明映射
        version_labels = {
            '3.13.1': '最新版',
            '3.12.8': '稳定推荐',
            '3.11.11': '兼容性好',
            '3.10.16': '老项目',
            '3.9.21': '遗留支持'
        }
        
        for i, ver in enumerate(versions):
            label_text = f"{ver}"
            if ver in version_labels:
                label_text = f"{ver} ({version_labels[ver]})"
            rb = ctk.CTkRadioButton(ver_grid, text=label_text, variable=self.version_var, value=ver)
            rb.grid(row=i // 2, column=i % 2, padx=10, pady=3, sticky="w")
        
        # 镜像选择 - 使用单选按钮
        mirror_frame = ctk.CTkFrame(self)
        mirror_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(mirror_frame, text="下载镜像源:", font=("bold", 13)).pack(anchor="w", pady=(10,5))
        
        mirror_grid = ctk.CTkFrame(mirror_frame, fg_color="transparent")
        mirror_grid.pack(fill="x", pady=5)
        
        self.mirror_var = tk.StringVar(value=self.manager.python_mirror)
        mirror_info = {
            'huawei': ('华为云镜像', '国内最快'),
            'npmmirror': ('NPM镜像', '淘宝源'),
            'official': ('官方源', '可能较慢')
        }
        
        col = 0
        for key, (name, desc) in mirror_info.items():
            rb = ctk.CTkRadioButton(mirror_grid, text=f"{name} ({desc})", 
                                     variable=self.mirror_var, value=key)
            rb.grid(row=0, column=col, padx=10, pady=3, sticky="w")
            col += 1

        
        # 进度条
        self.progress = ctk.CTkProgressBar(self, orientation="horizontal")
        self.progress.pack(fill="x", padx=20, pady=15)
        self.progress.set(0)
        
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack(pady=(0, 10))
        
        # 按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, fill="x", padx=20)
        
        self.download_btn = ctk.CTkButton(btn_frame, text="下载并安装", width=150, 
                                           fg_color="#4CAF50", hover_color="#388E3C",
                                           command=self.start_download)
        self.download_btn.pack(side="left", padx=10)
        
        self.stop_btn = ctk.CTkButton(btn_frame, text="停止", width=80,
                                       fg_color="gray", state="disabled",
                                       command=self.stop_download)
        self.stop_btn.pack(side="left", padx=5)
        
        # 新增：自动推荐版本按钮
        ctk.CTkButton(btn_frame, text="🧠 智能推荐", width=100,
                      fg_color="#FF9800", hover_color="#F57C00",
                      command=self.auto_recommend_version).pack(side="left", padx=10)
        
        ctk.CTkButton(btn_frame, text="使用系统 Python", width=120,
                      fg_color="#607D8B", hover_color="#455A64",
                      command=self.use_system_python).pack(side="right", padx=10)
        
        # 说明
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(pady=10, padx=20, fill="x")
        info_text = "说明:\n• 华为云镜像速度最快 (推荐)\n• 下载的是 Windows x64 嵌入式版本\n• 下载后会自动配置 pip"
        ctk.CTkLabel(info_frame, text=info_text, justify="left", 
                     text_color="gray", font=("Arial", 11)).pack(anchor="w")
    
    def start_download(self):
        if self.downloading: return
        self.downloading = True
        self.manager.reset_stop_flag()
        
        # 更新镜像选择 (现在直接使用 key)
        self.manager.python_mirror = self.mirror_var.get()
        
        self.download_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color="#D32F2F")
        self.progress_label.configure(text="正在准备下载...")
        
        version = self.version_var.get()
        threading.Thread(target=self._download_worker, args=(version,), daemon=True).start()
    
    def _download_worker(self, version):
        def log_cb(msg, t):
            self.after(0, lambda: self.progress_label.configure(text=msg))
            self.parent.safe_log(msg, t)
        def prog_cb(val):
            self.after(0, lambda: self.progress.set(val))
        
        old_log = self.manager.log_callback
        old_prog = self.manager.progress_callback
        self.manager.set_callbacks(log_cb, prog_cb)
        
        success = self.manager.download_python(version)
        
        self.manager.set_callbacks(old_log, old_prog)
        self.after(0, lambda: self._download_finished(success, version))
    
    def _download_finished(self, success, version):
        self.downloading = False
        self.download_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color="gray")
        
        if success:
            self.progress.set(1.0)
            self.progress_label.configure(text=f"Python {version} 安装成功！")
            self.status_label.configure(text=self.manager.get_current_python_info())
            messagebox.showinfo("下载成功", f"Python {version} 已成功下载并安装！\n\n点击确定返回主界面。", parent=self)
            self.destroy()  # 成功后自动关闭窗口
        else:
            if self.manager.stop_flag:
                self.progress_label.configure(text="下载已取消")
            else:
                self.progress_label.configure(text="下载失败，请检查网络")
                messagebox.showerror("失败", "下载失败，请检查网络连接或尝试其他镜像源", parent=self)
    
    def stop_download(self):
        self.manager.stop_current_task()
        self.progress_label.configure(text="正在取消...")
    
    def use_system_python(self):
        sys_python = shutil.which('python')
        if sys_python:
            # 弹出确认对话框
            if messagebox.askyesno("确认", f"检测到系统 Python:\n{sys_python}\n\n是否使用此 Python？", parent=self):
                self.manager.set_python_mode(True, sys_python)
                messagebox.showinfo("设置成功", f"已切换到系统 Python:\n{sys_python}", parent=self)
                self.destroy()  # 确认后自动关闭窗口
        else:
            # 弹出询问是否手动选择
            if messagebox.askyesno("未检测到", "未在系统 PATH 中检测到 Python。\n\n是否手动选择 python.exe 路径？", parent=self):
                path = filedialog.askopenfilename(
                    parent=self, title="选择 python.exe",
                    filetypes=[("Python Executable", "python.exe"), ("All Files", "*.*")]
                )
                if path:
                    self.manager.set_python_mode(True, path)
                    messagebox.showinfo("设置成功", f"已切换到指定 Python:\n{path}", parent=self)
                    self.destroy()  # 确认后自动关闭窗口

    def auto_recommend_version(self):
        """基于项目依赖智能推荐 Python 版本"""
        self.progress_label.configure(text="正在扫描项目依赖...")
        self.download_btn.configure(state="disabled")
        
        def worker():
            # 步骤1: 扫描依赖
            result = self.manager.generate_requirements(None, 'project')
            if len(result) == 3:
                ok, msg, packages = result
            else:
                ok, msg = result
                packages = []
            
            if not ok or not packages:
                self.after(0, lambda: self._recommend_finished(None, "未检测到第三方依赖，建议使用最新稳定版 Python 3.12.8"))
                return
            
            # 步骤2: 分析兼容性
            rec_ver, rec_msg = self.manager.analyze_package_compatibility(packages)
            self.after(0, lambda: self._recommend_finished(rec_ver, rec_msg, packages))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _recommend_finished(self, rec_ver, rec_msg, packages=None):
        self.download_btn.configure(state="normal")
        self.progress_label.configure(text="")
        
        if rec_ver:
            # 构建提示信息
            msg = f"依赖分析完成！\n\n"
            if packages:
                msg += f"检测到 {len(packages)} 个依赖包:\n"
                msg += ", ".join(packages[:8])
                if len(packages) > 8: msg += f" 等"
                msg += "\n\n"
            msg += f"{rec_msg}\n\n是否立即下载并安装推荐的 Python {rec_ver}？"
            
            if messagebox.askyesno("智能版本推荐", msg, parent=self):
                # 自动选中并开始下载
                self.version_var.set(rec_ver)
                self.start_download()
        else:
            messagebox.showinfo("分析结果", rec_msg, parent=self)

class EnvManagerWindow(ctk.CTkToplevel):

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.title("环境管理 - 批量清理")
        self.geometry("750x650")
        self.manager = manager
        self.parent = parent
        self.checkboxes = []
        self.scanning = False
        
        # 窗口置顶和模态设置
        self.transient(parent)  # 关联到父窗口
        self.grab_set()  # 模态窗口
        self.lift()  # 置于最前
        self.focus_force()  # 强制获取焦点

        
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(pady=10, padx=10, fill="x")
        btn_grid = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_grid.pack(fill="x", pady=5)
        ctk.CTkButton(btn_grid, text="扫描当前文件夹", command=self.start_simple_scan).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(btn_grid, text="全盘深度扫描", fg_color="#E64A19", hover_color="#D84315", command=self.start_full_scan).pack(side="left", padx=5, expand=True, fill="x")
        path_grid = ctk.CTkFrame(top_frame, fg_color="transparent")
        path_grid.pack(fill="x", pady=5)
        ctk.CTkLabel(path_grid, text="指定路径:").pack(side="left", padx=5)
        self.scan_path_entry = ctk.CTkEntry(path_grid)
        self.scan_path_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.scan_path_entry.insert(0, self.manager.project_path)
        ctk.CTkButton(path_grid, text="浏览", width=50, command=self.browse_scan_path).pack(side="left", padx=5)
        ctk.CTkButton(path_grid, text="扫描此路径", width=80, command=self.start_custom_scan).pack(side="left", padx=5)
        self.progress = ctk.CTkProgressBar(self, orientation="horizontal", mode="indeterminate")
        self.progress.pack(fill="x", padx=20, pady=5)
        self.progress.stop()
        self.progress_lbl = ctk.CTkLabel(self, text="")
        self.progress_lbl.pack(pady=(0,5))
        ctk.CTkLabel(self, text="检测到的虚拟环境 (勾选以删除):", font=("bold", 14)).pack(pady=(5, 5))
        self.scroll = ctk.CTkScrollableFrame(self, width=700, height=350)
        self.scroll.pack(pady=5, padx=10, fill="both", expand=True)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, fill="x", padx=20)
        ctk.CTkButton(btn_frame, text="全选", width=80, command=self.select_all).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="反选", width=80, command=self.deselect_all).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="删除选中环境", width=150, fg_color="#D32F2F", hover_color="#B71C1C", command=self.delete_selected).pack(side="right", padx=10)
        self.stop_scan_btn = ctk.CTkButton(btn_frame, text="停止扫描", width=80, fg_color="gray", command=self.stop_scanning, state="disabled")
        self.stop_scan_btn.pack(side="left", padx=5)
        self.pause_scan_btn = ctk.CTkButton(btn_frame, text="暂停", width=80, fg_color="#F9A825", hover_color="#FBC02D", command=self.toggle_pause, state="disabled")
        self.pause_scan_btn.pack(side="left", padx=5)
        
        # 初始化时自动同步主窗口路径，解决了"检测不到新建环境"的问题
        current_path = self.manager.project_path
        self.scan_path_entry.delete(0, "end"); self.scan_path_entry.insert(0, current_path)
        self.start_simple_scan()

    def browse_scan_path(self):
        p = filedialog.askdirectory(parent=self)
        if p:
            self.scan_path_entry.delete(0, "end"); self.scan_path_entry.insert(0, p)

    def start_simple_scan(self): 
        # 确保使用输入框中的最新路径
        p = self.scan_path_entry.get()
        if p and os.path.exists(p):
            self.manager.project_path = p
        self._start_scan_thread(mode="simple", path=self.manager.project_path)
    def start_custom_scan(self):
        p = self.scan_path_entry.get()
        if p: self._start_scan_thread(mode="recursive", path=p)
    def start_full_scan(self):
        if messagebox.askyesno("高能预警", "全盘扫描将搜索电脑中所有的盘符。\n\n1. 过程可能需要几分钟。\n2. 请务必仔细核对路径，不要误删系统环境！\n\n是否继续？", parent=self):
            drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")] if sys.platform == 'win32' else ["/"]
            self._start_scan_thread(mode="recursive_list", path=drives)
    def stop_scanning(self):
        self.manager.stop_current_task()
        self.progress_lbl.configure(text="正在停止扫描...")
    
    def toggle_pause(self):
        if self.manager.pause_flag:
            self.manager.resume_task()
            self.pause_scan_btn.configure(text="暂停")
            self.progress_lbl.configure(text="扫描中...")
        else:
            self.manager.pause_task()
            self.pause_scan_btn.configure(text="继续")
            self.progress_lbl.configure(text="扫描已暂停")

    def _start_scan_thread(self, mode, path):
        if self.scanning: return
        self.scanning = True; self.manager.reset_stop_flag()
        self.progress.start()
        self.stop_scan_btn.configure(state="normal", fg_color="#D32F2F")
        self.pause_scan_btn.configure(state="normal")
        self.progress_lbl.configure(text="正在扫描中，请稍候...")
        for widget in self.scroll.winfo_children(): widget.destroy()
        threading.Thread(target=self._scan_worker, args=(mode, path), daemon=True).start()

    def _scan_worker(self, mode, path):
        venvs = []
        try:
            if mode == "simple": venvs = self.manager.scan_simple_venvs(path)
            elif mode == "recursive": venvs = self.manager.scan_recursive_venvs(path)
            elif mode == "recursive_list": venvs = self.manager.scan_recursive_venvs(path)
        except Exception: pass
        self.after(0, lambda: self._scan_finished(venvs))

class HelpWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Python环境配置哈哈 4.0 - 使用手册")
        self.geometry("700x750")
        
        # 窗口置顶和模态设置
        self.transient(parent)
        self.grab_set()
        self.lift()
        self.focus_force()
        
        # 容器
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        ctk.CTkLabel(scroll, text=" Python环境配置哈哈 4.0 使用手册 ", font=("bold", 24), 
                     text_color="#4fc3f7").pack(pady=20)
        
        # 内容区域
        docs = [
            (" 👋 欢迎使用 Python环境配置哈哈 4.0", 
             '专为 Python 初学者打造的"一键式"环境配置神器。\n'
             "再也不用担心装包报错、版本冲突或者搞不清 pip 和 conda 了！\n"
             "本工具帮你自动完成：下载Python → 创建虚拟环境 → 分析依赖 → 安装库。"),

            (" 🆕 4.0 版本新功能", 
             "【PyTorch 智能版本选择】\n"
             "当检测到项目需要 PyTorch 时，自动弹出版本选择：\n"
             "  • GPU 版本：需要 NVIDIA 显卡 + CUDA\n"
             "  • CPU 版本：更稳定，推荐无显卡用户选择\n"
             "  使用清华镜像加速下载，速度飞快！\n\n"
             "【Jupyter Notebook 支持】\n"
             "  • 支持选择和扫描 .ipynb 文件\n"
             "  • 自动安装 ipykernel（VSCode 运行必需）\n"
             "  • 自动生成 Jupyter 启动脚本"),

            (" 🚀 快速上手：只需 3 步", 
             "【第一步：选择项目】\n"
             '点击"浏览"按钮，选择你的 Python 项目文件夹。\n'
             "程序会自动推荐一个环境名称（如 项目名_env）。\n\n"
             "【第二步：点击开始】\n"
             '点击"开始一键配置"大按钮。软件会自动执行：\n'
             "  ① 扫描项目中的 .py/.ipynb 文件，分析依赖\n"
             "  ② 生成 requirements.txt 依赖清单\n"
             "  ③ 智能推荐兼容的 Python 版本\n"
             "  ④ 创建独立的虚拟环境\n"
             "  ⑤ 通过镜像源快速安装所有依赖\n\n"
             "【第三步：开始使用】\n"
             "配置完成后，项目目录会生成：\n"
             "  • activate_env.bat - 双击激活环境\n"
             "  • run_xxx.bat - 一键运行脚本"),

            (" 🐍 Python 版本管理",
             "点击【Python 管理 / 智能推荐】按钮，可以：\n\n"
             "• 下载指定版本：支持 3.9 ~ 3.13 多个版本\n"
             "• 选择镜像源：华为云（最快）、NPM镜像、官方源\n"
             "• 智能推荐：根据项目依赖自动分析最佳版本\n"
             "• 使用系统Python：如果电脑已安装Python，可直接使用\n\n"
             "💡 小贴士：Python 3.11 兼容性最好，推荐新手使用"),

            (" 📦 依赖分析原理",
             "程序通过正则表达式扫描代码中的 import 语句：\n\n"
             "• 自动识别第三方库（排除标准库如 os、sys、json）\n"
             "• 智能映射包名（如 cv2 → opencv-python）\n"
             "• 推断隐式依赖（如 pandas.to_excel 自动添加 openpyxl）\n"
             "• 支持扫描 .ipynb Notebook 文件\n"
             "• 检测到 Notebook 自动添加 ipykernel 和 jupyter"),

            (" 🛠️ 实用工具箱", 
             "【环境管理 / 批量删除】\n"
             "• 扫描当前文件夹下的虚拟环境\n"
             "• 全盘深度扫描（清理旧项目的残留环境）\n"
             "• 勾选后批量删除，释放磁盘空间\n\n"
             "【彻底清理项目】\n"
             "删除虚拟环境、脚本文件和工具缓存"),

            (" ⚠️ 常见错误及解决方案", 
             "【错误】[WinError 1114] 动态链接库(DLL)初始化例程失败\n\n"
             "原因：PyTorch 需要 Visual C++ 运行时库\n\n"
             "解决方案：\n"
             "1. 下载安装 Visual C++ Redistributable 2015-2022：\n"
             "   https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
             "2. 安装完成后重启电脑\n"
             "3. 重新运行程序\n\n"
             "或者重新配置环境时选择 CPU 版本的 PyTorch！"),

            (" 🔍 其他常见问题", 
             "Q: 配置失败怎么办？\n"
             "A: 查看日志窗口错误信息，尝试切换镜像源或Python版本\n\n"
             "Q: 如何更新已安装的库？\n"
             "A: 双击 activate_env.bat，执行 pip install --upgrade 包名\n\n"
             "Q: 可以同时配置多个项目吗？\n"
             "A: 可以！每个项目有独立的虚拟环境，互不影响。\n\n"
             "Q: 下载的 Python 和官网的有区别吗？\n"
             "A: 无区别！都是官方版本，只是本软件下载的是绑定的便携版。")
        ]
        
        for title, text in docs:
            # 章节标题
            f = ctk.CTkFrame(scroll, fg_color="#2b2b2b")
            f.pack(fill="x", pady=10, padx=5)
            ctk.CTkLabel(f, text=title, font=("bold", 15), text_color="#81d4fa").pack(anchor="w", padx=10, pady=5)
            
            # 章节内容
            content = ctk.CTkLabel(scroll, text=text, justify="left", 
                                   wraplength=600, font=("Microsoft YaHei", 12))
            content.pack(anchor="w", padx=20, pady=5)
            
        # 底部
        ctk.CTkLabel(scroll, text="--- 祝你编程愉快 哈哈 ---", text_color="gray").pack(pady=30)
        
        # 关闭按钮
        ctk.CTkButton(self, text="我知道了", command=self.destroy).pack(pady=10)


    def _scan_finished(self, venvs):
        self.scanning = False; self.progress.stop()
        self.stop_scan_btn.configure(state="disabled", fg_color="gray")
        self.pause_scan_btn.configure(state="disabled", text="暂停")
        self.checkboxes.clear()
        
        # 即使停止了，也显示已找到的结果
        if self.manager.stop_flag: 
            self.progress_lbl.configure(text=f"扫描已停止，显示部分结果 ({len(venvs)} 个)")
        elif not venvs: 
            self.progress_lbl.configure(text="未发现虚拟环境")
            return
        else:
            self.progress_lbl.configure(text=f"扫描完成，共发现 {len(venvs)} 个环境")
            
        for v in venvs:
            name = v['name']; path = v['path']
            row = ctk.CTkFrame(self.scroll, fg_color="transparent"); row.pack(fill="x", pady=2, padx=5)
            var = tk.BooleanVar(); cb = ctk.CTkCheckBox(row, text=name, variable=var, width=100); cb.pack(side="left", anchor="w")
            ctk.CTkLabel(row, text=path, text_color="gray", font=("Arial", 11)).pack(side="left", padx=10)
            self.checkboxes.append({'path': path, 'var': var})

    def select_all(self): 
        for item in self.checkboxes: item['var'].set(True)
    def deselect_all(self): 
        for item in self.checkboxes: item['var'].set(False)
    def delete_selected(self):
        to_delete = [item['path'] for item in self.checkboxes if item['var'].get()]
        if not to_delete: messagebox.showinfo("提示", "请先选择要删除的环境", parent=self); return
        if not messagebox.askyesno("严重警告", f"确定要永久删除这 {len(to_delete)} 个环境吗？\n\n这些文件夹及其内容将被彻底清空！\n操作不可恢复！", parent=self): return
        self.destroy(); self.parent.start_batch_delete(to_delete)

class App(ctk.CTk):
    def __init__(self):
        # 初始化前先关闭启动画面，避免 dual-Tk 冲突
        self._close_splash_immediately()
        super().__init__()
        self.manager = PythonEnvManager()
        ctk.set_appearance_mode(self.manager.theme)
        self.manager.set_callbacks(self.safe_log, self.update_progress)
        self.is_running = False
        try:
            icon_path = get_bundled_resource("icon.ico")
            if icon_path.exists(): self.iconbitmap(icon_path)
        except Exception: pass
        self.setup_ui()
        self.after(200, self.check_initial_python)
        self.after(500, self.load_data)
    
    # ==================== IDE 功能已禁用 (v2.0) ====================
    # def open_ide(self, force_choose=False):
    #     """智能打开 IDE - 自动快速启动或选择项目
    #     
    #     Args:
    #         force_choose: 如果为True，强制让用户选择项目（按住Shift点击时）
    #     """
    #     current_project = None
    #     
    #     # 智能模式1: 如果有历史记录且不是强制选择，直接快速启动
    #     if not force_choose and self.manager.last_ide_project and os.path.exists(self.manager.last_ide_project):
    #         # 快速启动模式
    #         current_project = self.manager.last_ide_project
    #         self.safe_log(f"⚡ 快速启动 IDE: {Path(current_project).name}", "info")
    #     
    #     # 智能模式2: 检查主界面是否已选择项目
    #     if not current_project:
    #         path_input = self.path_entry.get().strip()
    #         if path_input and os.path.exists(path_input) and not force_choose:
    #             current_project = path_input
    #     
    #     # 智能模式3: 需要用户选择项目
    #     if not current_project:
    #         # 首次使用或强制选择新项目
    #         choice = messagebox.askyesnocancel(
    #             "打开 IDE",
    #             "请选择项目文件夹\n\n"
    #             "【是】- 浏览选择项目文件夹\n"
    #             "【否】- 在当前目录打开 IDE\n"
    #             "【取消】- 返回\n\n"
    #             "💡 提示: 选择后下次可直接快速启动",
    #             parent=self
    #         )
    #         
    #         if choice is None:  # 取消
    #             return
    #         elif choice:  # 是 - 浏览选择
    #             project_dir = filedialog.askdirectory(title="选择项目文件夹", parent=self)
    #             if not project_dir:
    #                 return
    #             current_project = project_dir
    #         else:  # 否 - 当前目录
    #             current_project = os.getcwd()
    #     
    #     # 确保项目路径有效
    #     if not os.path.isdir(current_project):
    #         messagebox.showerror("错误", f"无效的项目路径：{current_project}", parent=self)
    #         return
    #     
    #     # 智能检测虚拟环境
    #     venv_path = None
    #     
    #     # 1. 尝试使用输入框中的环境名
    #     venv_name = self.venv_name_entry.get().strip()
    #     if venv_name:
    #         test_venv = Path(current_project) / venv_name
    #         if self.manager._is_venv(test_venv):
    #             venv_path = test_venv
    #     
    #     # 2. 如果没找到，尝试扫描项目下的环境
    #     if not venv_path:
    #         venvs = self.manager.scan_simple_venvs(current_project)
    #         if venvs:
    #             venv_path = Path(venvs[0]['path'])
    #     
    #     # 3. 如果还是没有，尝试使用上次的 IDE 环境（如果项目相同）
    #     if not venv_path and self.manager.last_ide_venv and current_project == self.manager.last_ide_project:
    #         last_venv = Path(self.manager.last_ide_venv)
    #         if last_venv.exists() and self.manager._is_venv(last_venv):
    #             venv_path = last_venv
    #     
    #     # 保存本次 IDE 配置供下次快速启动
    #     self.manager.last_ide_project = current_project
    #     self.manager.last_ide_venv = str(venv_path) if venv_path else None
    #     self.manager.save_settings()
    #     
    #     # 打开 IDE
    #     self.safe_log(f"正在启动 IDE: {Path(current_project).name}", "info")
    #     if venv_path:
    #         self.safe_log(f"已加载虚拟环境: {venv_path.name}", "success")
    #     else:
    #         self.safe_log("使用系统 Python（未检测到虚拟环境）", "info")
    #     
    #     MiniIDEWindow(self, current_project, venv_path)
    #     self.withdraw()
    # ==================== IDE 功能已禁用结束 ====================

    def _close_splash_immediately(self):
        global _splash
        if _splash:
            try:
                _splash.withdraw() # 先隐藏
                _splash.destroy()
            except: pass
            _splash = None

    def setup_ui(self):
        self.title("Python环境配置哈哈5.0") 
        self.geometry("900x750")
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent"); top.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(top, text="项目路径:").pack(side="left")
        self.path_entry = ctk.CTkEntry(top, width=350); self.path_entry.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(top, text="浏览", width=60, command=self.browse).pack(side="left")
        
        
        # IDE 按钮已禁用 (v2.0)
        # ctk.CTkButton(
        #     top, 
        #     text="💻 打开 IDE", 
        #     width=90, 
        #     fg_color="#673AB7", 
        #     hover_color="#512DA8", 
        #     command=self.open_ide
        # ).pack(side="right", padx=(5, 0))
        
        ctk.CTkButton(top, text="📚 手册", width=60, fg_color="#4CAF50", hover_color="#388E3C", command=self.open_help).pack(side="right", padx=5)
        ctk.CTkButton(top, text="⚙️ 设置", width=60, fg_color="gray", command=self.open_settings).pack(side="right", padx=5)
        
        main = ctk.CTkFrame(self, fg_color="transparent"); main.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        main.columnconfigure(0, weight=1); main.columnconfigure(1, weight=1); main.rowconfigure(0, weight=1)
        left = ctk.CTkFrame(main); left.grid(row=0, column=0, padx=(0,10), sticky="nsew")
        ctk.CTkLabel(left, text="配置", font=("bold", 16)).pack(pady=10)
        ctk.CTkLabel(left, text="环境名称 (自动推荐):", anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.venv_name_entry = ctk.CTkEntry(left); self.venv_name_entry.pack(fill="x", padx=20, pady=5); self.venv_name_entry.insert(0, ".venv")
        self.scan_var = tk.StringVar(value="project")
        ctk.CTkRadioButton(left, text="扫描项目", variable=self.scan_var, value="project", command=self.toggle_file).pack(anchor="w", padx=20, pady=5)
        ctk.CTkRadioButton(left, text="扫描文件", variable=self.scan_var, value="single", command=self.toggle_file).pack(anchor="w", padx=20, pady=5)
        self.file_entry = ctk.CTkEntry(left, placeholder_text="主运行文件 (.py)"); self.file_entry.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(left, text="选择文件", command=self.browse_file).pack(padx=20, pady=5, anchor="e")
        ctk.CTkButton(left, text="环境管理 / 批量删除", fg_color="#FF9800", hover_color="#F57C00", command=self.open_env_manager).pack(fill="x", padx=20, pady=(20, 5))
        ctk.CTkButton(left, text="Python 管理 / 智能推荐", fg_color="#00ACC1", hover_color="#00838F", command=self.open_python_manager).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(left, text="彻底清理项目", fg_color="#D32F2F", hover_color="#B71C1C", command=self.clean).pack(fill="x", padx=20, pady=5)
        right = ctk.CTkFrame(main); right.grid(row=0, column=1, padx=(10,0), sticky="nsew"); right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="执行日志", font=("bold", 16)).grid(row=0, column=0, pady=10)
        self.log_box = ctk.CTkTextbox(right); self.log_box.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.status_lbl = ctk.CTkLabel(right, text="就绪", anchor="w"); self.status_lbl.grid(row=2, column=0, padx=10, sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(self, orientation="horizontal", height=15); self.progress_bar.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew"); self.progress_bar.set(0)
        self.start_btn = ctk.CTkButton(self, text="开始一键配置", font=("bold", 18), height=50, command=self.start_process); self.start_btn.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")



    def check_initial_python(self):
        """启动时静默检查 Python 配置状态（不再弹窗询问）"""
        # 只在日志中显示当前配置，用户可通过"Python管理"按钮更改
        self.safe_log(f"Python 配置: {self.manager.get_current_python_info()}", "info")

    def open_settings(self):
        if messagebox.askyesno("重置", "是否重置设置？\n这将清除 Python 配置，下次使用时需重新选择。"):
            if SETTINGS_FILE.exists(): SETTINGS_FILE.unlink()
            self.manager.load_settings()
            self.safe_log("设置已重置", "warning")
            self.safe_log(f"Python 配置: {self.manager.get_current_python_info()}", "info")


    def open_python_manager(self): 
        # 同步路径
        current_path = self.path_entry.get()
        if current_path and os.path.isdir(current_path):
            self.manager.set_project_path(current_path)
            
        if not self.manager.project_path:
            messagebox.showwarning("提示", "请先选择项目文件夹！", parent=self)
            return
            
        PythonManagerWindow(self, self.manager)
    def open_env_manager(self): 
        # 非常重要：打开环境管理前，强制同步当前输入框的路径到 manager
        # 这样能解决用户修改了路径但只点"环境管理"导致扫描旧路径的问题
        current_path = self.path_entry.get()
        if current_path and os.path.isdir(current_path):
            self.manager.set_project_path(current_path)
        elif not self.manager.project_path:
            # 如果没有有效路径且 manager 也没有路径，提示用户
            messagebox.showwarning("提示", "请先选择项目文件夹！", parent=self)
            return
            
        EnvManagerWindow(self, self.manager)
    def open_help(self): HelpWindow(self)
    def safe_log(self, msg, type="info"): self.after(0, lambda: self._log(msg, type))
    def _log(self, msg, type):
        self.log_box.configure(state="normal")
        prefix = {"success": "✅", "error": "❌", "info": "ℹ️", "warning": "⚠️"}.get(type, "")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {prefix} {msg}\n")
        self.log_box.see("end"); self.log_box.configure(state="disabled")
        if self.progress_bar._mode != "indeterminate": self.status_lbl.configure(text=f"状态: {msg}")
    def update_progress(self, value): 
        if self.progress_bar._mode != "indeterminate": self.after(0, lambda: self.progress_bar.set(value))
    
    def load_data(self): 
        # 启动时不设置默认路径，让用户自己选择
        # 如果 project_path 为空，只显示提示信息
        if self.manager.project_path:
            self.path_entry.insert(0, self.manager.project_path)
            self.refresh_files()
            self.check_venv()
        else:
            self.safe_log("请先选择项目文件夹", "info")
            self.status_lbl.configure(text="请选择项目路径")
    
    def browse(self):
        p = filedialog.askdirectory()
        if p and self.manager.set_project_path(p):
            self.path_entry.delete(0, "end"); self.path_entry.insert(0, p)
            folder_name = Path(p).name; safe_name = folder_name.replace(" ", "_") + "_env"
            self.venv_name_entry.delete(0, "end"); self.venv_name_entry.insert(0, safe_name)
            self.refresh_files(); self.check_venv()
            self.safe_log(f"已选择项目: {folder_name}", "success")
    
    def refresh_files(self):
        # File scanning - no longer need to update combo since we use entry widget
        pass
    def toggle_file(self): 
        # Toggle file entry state based on scan mode
        pass
    def check_venv(self):
        # 如果没有项目路径，不检查
        if not self.manager.project_path:
            return
        venv_name = self.venv_name_entry.get().strip() or ".venv"; info = self.manager.get_venv_info(venv_name)
        if info['exists']: self.safe_log(f"检测到环境 ({venv_name}): {info['version']}", "info")
        else: self.safe_log(f"环境 ({venv_name}) 未创建", "info")

    def browse_file(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="选择主运行文件",
            filetypes=[("Python Files", "*.py;*.pyw;*.ipynb"), ("Jupyter Notebook", "*.ipynb"), ("All Files", "*.*")]
        )
        if filename:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filename)
            self.scan_var.set("single")
            self.toggle_file()

    def start_process(self):
        if self.is_running:
            self.manager.stop_current_task(); self.start_btn.configure(text="正在停止...", state="disabled")
        else:
            # 检查是否已选择项目路径
            if not self.manager.project_path:
                messagebox.showwarning("提示", '请先选择项目文件夹！\n\n点击"浏览"按钮选择你的 Python 项目所在目录。', parent=self)
                return
            
            self.is_running = True; self.manager.reset_stop_flag()
            self.start_btn.configure(text="🛑 停止", fg_color="#D32F2F", hover_color="#B71C1C")
            self.status_lbl.configure(text="正在配置中，请勿退出..."); self.progress_bar.configure(mode="indeterminate"); self.progress_bar.start()
            threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        try:
            target = self.file_entry.get().strip() if self.scan_var.get() == "single" else None
            # 如果是相对路径，转为绝对路径（如果有需要，不过 Entry 里通常是 browse 出来的绝对路径）
            if target and not Path(target).is_absolute():
                 target = str(Path(self.manager.project_path) / target)
            
            venv_name = self.venv_name_entry.get().strip()
            if not venv_name: venv_name = ".venv"
            
            # 步骤 1: 先扫描依赖（在确定Python版本之前）
            self.safe_log("=" * 40, "info")
            self.safe_log("步骤 1/5: 扫描项目依赖...", "info")
            result = self.manager.generate_requirements(target, self.scan_var.get())
            
            # 处理返回值（可能是2个或3个值）
            if len(result) == 3:
                ok, msg, packages = result
            else:
                ok, msg = result
                packages = []
            
            self.safe_log(msg, "success" if ok else "error")
            if not ok: return
            
            # 步骤 2: 智能分析 Python 版本兼容性
            self.safe_log("=" * 40, "info")
            self.safe_log("步骤 2/5: 分析依赖兼容性...", "info")
            
            recommended_version = None
            
            if packages:
                # 基于依赖包分析推荐版本
                rec_ver, rec_msg = self.manager.analyze_package_compatibility(packages)
                if rec_ver:
                    self.safe_log(rec_msg, "success")
                    recommended_version = rec_ver
                    
                    # 弹窗让用户确认推荐版本
                    confirm_msg = f"依赖分析完成！\n\n检测到 {len(packages)} 个依赖包:\n"
                    confirm_msg += ", ".join(packages[:5])
                    if len(packages) > 5: confirm_msg += f" 等共 {len(packages)} 个"
                    confirm_msg += f"\n\n{rec_msg}\n\n是否使用推荐版本 Python {rec_ver}？\n（选择'否'将使用当前已配置的 Python）"
                    
                    # 在主线程弹窗
                    use_recommended = [None]  # 用列表存储结果
                    def ask_user():
                        use_recommended[0] = messagebox.askyesno("智能版本推荐", confirm_msg)
                    self.after(0, ask_user)
                    
                    # 等待用户响应
                    import time
                    while use_recommended[0] is None:
                        time.sleep(0.1)
                    
                    if not use_recommended[0]:
                        self.safe_log("用户选择使用当前 Python 配置", "info")
                        recommended_version = None
                else:
                    self.safe_log(rec_msg, "info")
            else:
                # 没有第三方依赖，尝试从项目文件检测
                detected, source = self.manager.detect_required_python_version()
                if detected:
                    recommended_version = detected
                    self.safe_log(f"从 {source} 检测到版本要求: Python {recommended_version}", "info")
                else:
                    self.safe_log("无特殊版本要求，将使用默认配置", "info")
            
            # 步骤 3: 确保 Python 可用 (自动下载)
            self.safe_log("=" * 40, "info")
            self.safe_log("步骤 3/5: 准备 Python 环境...", "info")
            if not self.manager.ensure_python_available(recommended_version):
                self.safe_log("Python 环境准备失败！", "error")
                return
            self.safe_log("Python 环境就绪 ✓", "success")
            
            # 步骤 4: 创建虚拟环境
            self.safe_log("=" * 40, "info")
            self.safe_log("步骤 4/5: 创建虚拟环境...", "info")
            ok, msg = self.manager.create_venv(recommended_version, venv_name)
            self.safe_log(msg, "success" if ok else "error"); 
            if not ok: return
            
            # 步骤 5: 安装依赖
            self.safe_log("=" * 40, "info")
            self.safe_log("步骤 5/5: 安装项目依赖...", "info")
            
            # --- PyTorch 版本选择 ---
            # 检测是否需要安装 PyTorch
            torch_packages = {'torch', 'pytorch', 'torchvision', 'torchaudio'}
            has_torch = any(pkg.lower() in torch_packages for pkg in packages)
            
            pytorch_source = None  # None = 使用默认 PyPI, 否则使用特定源
            if has_torch:
                # 在主线程弹窗询问
                pytorch_choice = [None]  # 用列表存储结果
                def ask_pytorch():
                    result = messagebox.askyesnocancel(
                        "PyTorch 版本选择",
                        "检测到项目需要 PyTorch！\n\n"
                        "请选择安装版本：\n\n"
                        "【是】→ GPU 版本 (需要 NVIDIA 显卡 + CUDA)\n"
                        "【否】→ CPU 版本 (推荐，更稳定)\n"
                        "【取消】→ 使用默认版本 (不推荐)\n\n"
                        "💡 提示：如果没有 NVIDIA 显卡，请选择 CPU 版本！\n"
                        "GPU 版本约 2.5GB，CPU 版本约 150MB。"
                    )
                    pytorch_choice[0] = result
                self.after(0, ask_pytorch)
                
                # 等待用户响应
                import time
                while pytorch_choice[0] is None:
                    time.sleep(0.1)
                    if pytorch_choice[0] is not None:
                        break
                    # 超时检测（防止死循环）
                    time.sleep(0.05)
                
                if pytorch_choice[0] == True:  # 是 = GPU
                    pytorch_source = "https://mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/cu124"
                    self.safe_log("用户选择: GPU 版本 (CUDA 12.4) - 清华镜像加速", "info")
                elif pytorch_choice[0] == False:  # 否 = CPU
                    pytorch_source = "https://mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/cpu"
                    self.safe_log("用户选择: CPU 版本 (推荐) - 清华镜像加速", "info")
                else:  # 取消 = 默认
                    self.safe_log("用户选择: 使用 PyPI 默认版本", "info")
            
            # 安装依赖
            ok, msg = self.manager.install_dependencies(venv_name, pytorch_source=pytorch_source)
            if ok:
                self.safe_log("依赖安装完成 ✓", "success")
            else:
                self.safe_log(f"安装失败: {msg[:100]}...", "error"); 
                return
            
            self.manager.create_scripts(target, venv_name)
            self.safe_log("=" * 40, "info")
            self.safe_log("🎉 全部完成！环境配置成功！", "success")
            self.safe_log(f"虚拟环境: {venv_name}", "info")
            self.safe_log(f"Python 版本: {self.manager.get_current_python_info()}", "info")
            self.after(0, self.check_venv)
        except Exception as e: self.safe_log(f"配置失败: {str(e)}", "error")
        finally:
            self.is_running = False
            self.after(0, lambda: self.progress_bar.stop()); self.after(0, lambda: self.progress_bar.configure(mode="determinate")); self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.start_btn.configure(text="开始一键配置", state="normal", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"]))
            self.after(0, lambda: self.status_lbl.configure(text="就绪"))


    def start_batch_delete(self, venv_list):
        self.start_btn.configure(state="disabled"); self.progress_bar.set(0); self.is_running = True
        threading.Thread(target=self._batch_delete_thread, args=(venv_list,), daemon=True).start()

    def _batch_delete_thread(self, venv_list):
        try:
            self.manager.reset_stop_flag(); count = len(venv_list)
            for i, venv in enumerate(venv_list):
                if self.manager.stop_flag: break
                self.safe_log(f"正在删除 ({i+1}/{count})...", "info")
                ok, msg = self.manager.delete_venv_with_progress(venv)
                self.safe_log(f"{Path(venv).name}: {msg}", "success" if ok else "error")
                self.update_progress((i + 1) / count)
            self.safe_log("批量删除完成", "success"); self.after(0, self.check_venv)
        except Exception as e: self.safe_log(f"删除出错: {e}", "error")
        finally: self.is_running = False; self.after(0, lambda: self.start_btn.configure(state="normal"))

    def clean(self):
        # 检查是否已选择项目路径
        if not self.manager.project_path:
            messagebox.showwarning("提示", '请先选择项目文件夹！', parent=self)
            return
            
        if not messagebox.askyesno("确认", "彻底清理文件？\n这将删除所有虚拟环境、脚本、配置文件及 env_tools 工具包。"):
            return
        
        # 开始清理 - 使用线程和进度条
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_lbl.configure(text="正在清理项目...")
        threading.Thread(target=self._clean_thread, daemon=True).start()
    
    def _clean_thread(self):
        """清理线程"""
        try:
            # 定义进度回调
            def progress_cb(value):
                self.after(0, lambda v=value: self.progress_bar.set(v))
            
            ok, msg = self.manager.clean_project(progress_callback=progress_cb)
            self.safe_log(msg, "success" if ok else "error")
            
            # 刷新设置
            self.manager.load_settings()
            self.after(0, self.check_venv)
            
        except Exception as e:
            self.safe_log(f"清理出错: {e}", "error")
        finally:
            self.is_running = False
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            self.after(0, lambda: self.status_lbl.configure(text="清理完成"))

if __name__ == "__main__":
    app = App()
    app.mainloop()
