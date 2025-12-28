import os
import sys
import tkinter
from pathlib import Path
import PyInstaller.__main__

def build():
    # 1. 获取当前 Python 环境的 Tcl/Tk 路径
    # 这会直接询问当前运行的 Python 正在使用的库路径，确保版本绝对匹配
    try:
        root = tkinter.Tk()
        tcl_root = root.tk.call('info', 'library')
        tk_root = root.tk.call('info', 'library').replace('tcl', 'tk') # 通常 tk 和 tcl 平级，或者通过 variable tk_library 获取
        # 更稳健的方法：
        tk_root = root.tk.call('set', 'tk_library')
        
        print(f"Found Tcl at: {tcl_root}")
        print(f"Found Tk at: {tk_root}")
        
        tcl_path = Path(tcl_root)
        tk_path = Path(tk_root)
        
        if not tcl_path.exists():
            print(f"Warning: Tcl path {tcl_path} does not exist!")
        if not tk_path.exists():
            print(f"Warning: Tk path {tk_path} does not exist!")
            
    except Exception as e:
        print(f"Error finding Tcl/Tk: {e}")
        return

    # 2. 构造数据添加参数 --add-data "源路径;目标路径"
    # 我们将它们分别映射到 _internal/tcl 和 _internal/tk (对于 onedir)
    # 对于 onefile，它们会被解压到临时目录的 tcl 和 tk 文件夹
    # 关键：我们需要设置 TCL_LIBRARY 和 TK_LIBRARY 环境变量在运行时指向这里
    # 但 PyInstaller 的 runtime hook 应该能处理，只要文件夹在 data 里
    
    datas = [
        f'{str(tcl_path)};tcl',
        f'{str(tk_path)};tk'
    ]
    
    # 3. 构造打包参数
    args = [
        'main.py',
        '--name=机器学习哈哈1.0',
        '--onefile',
        '--windowed',
        '--noconfirm',
        '--clean',
    ]
    
    # 添加数据
    for d in datas:
        args.append(f'--add-data={d}')
        
    # 4. 执行打包
    print("Starting build with fixed paths...")
    PyInstaller.__main__.run(args)

if __name__ == '__main__':
    build()
