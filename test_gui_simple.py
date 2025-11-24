#!/usr/bin/env python3
"""最简单的 GUI 测试 - 不导入 recorder"""
import sys
import os
import tkinter as tk
from pathlib import Path

print("开始测试...")

# 修复 PyInstaller 打包后的路径问题
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
    os.chdir(application_path)
    print(f"打包环境，工作目录: {application_path}")
else:
    application_path = Path(__file__).parent
    print(f"开发环境，工作目录: {application_path}")

print("创建窗口...")
try:
    root = tk.Tk()
    root.title("测试窗口")
    root.geometry("400x300")
    
    label = tk.Label(root, text="如果看到这个窗口，说明基本功能正常", font=("Arial", 14))
    label.pack(pady=50)
    
    info_label = tk.Label(root, text=f"工作目录: {Path.cwd()}", font=("Arial", 10))
    info_label.pack()
    
    def on_close():
        print("窗口关闭")
        root.quit()
    
    root.protocol("WM_DELETE_WINDOW", on_close)
    print("窗口已创建，进入主循环...")
    root.mainloop()
    print("测试完成！")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


