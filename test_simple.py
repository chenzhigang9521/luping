#!/usr/bin/env python3
"""最简单的测试版本"""
import sys
import os
from pathlib import Path

print("1. 导入 sys, os, pathlib - OK")

try:
    import tkinter as tk
    print("2. 导入 tkinter - OK")
except Exception as e:
    print(f"2. 导入 tkinter 失败: {e}")
    sys.exit(1)

try:
    from pathlib import Path
    print("3. 导入 pathlib - OK")
except Exception as e:
    print(f"3. 导入 pathlib 失败: {e}")

try:
    import cv2
    print("4. 导入 cv2 - OK")
except Exception as e:
    print(f"4. 导入 cv2 失败: {e}")

try:
    import mss
    print("5. 导入 mss - OK")
except Exception as e:
    print(f"5. 导入 mss 失败: {e}")

try:
    import numpy as np
    print("6. 导入 numpy - OK")
except Exception as e:
    print(f"6. 导入 numpy 失败: {e}")

print("\n尝试创建 tkinter 窗口...")
try:
    root = tk.Tk()
    root.title("测试")
    root.geometry("300x200")
    label = tk.Label(root, text="如果看到这个窗口，说明基本功能正常")
    label.pack(pady=50)
    print("窗口创建成功，显示 3 秒后关闭...")
    root.after(3000, root.quit)
    root.mainloop()
    print("测试完成！")
except Exception as e:
    print(f"创建窗口失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


