"""
录屏软件 GUI界面
"""
import sys
import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import time
import subprocess
import tkinter.font as tkfont
import tempfile
import shutil

# 修复 PyInstaller 打包后的路径问题
if getattr(sys, 'frozen', False):
    # 如果是打包后的应用
    # 在 PyInstaller 的 onefile 模式下，运行时资源被解压到 sys._MEIPASS
    # 在 onedir 模式资源与 exe 同目录。优先使用 _MEIPASS（若存在），否则使用 exe 的目录。
    if hasattr(sys, '_MEIPASS'):
        application_path = Path(sys._MEIPASS)
    else:
        application_path = Path(sys.executable).parent
    try:
        os.chdir(application_path)
    except Exception:
        pass
else:
    # 如果是开发环境
    application_path = Path(__file__).parent.parent


def _extract_and_register_embedded_fonts(app_path: Path):
    """在创建 Tk 之前提取并注册嵌入字体（onefile 或 onedir）。
    - 将 `app_path / 'fonts'` 中的 ttf 文件复制到临时目录（确保可写路径），
      然后在 Windows 上使用 AddFontResourceExW 注册为进程私有字体。
    - 返回临时字体目录 Path 或 None。
    """
    # Support PyInstaller onedir layout where data files are placed in _internal
    internal_dir = Path(app_path) / '_internal'
    possible_fonts = [Path(app_path) / 'fonts', internal_dir / 'fonts']
    # decide where to write log: prefer _internal if present
    if internal_dir.exists() and internal_dir.is_dir():
        log_path = internal_dir / 'font_register.log'
    else:
        log_path = Path(app_path) / 'font_register.log'

    try:
        fonts_dir = None
        with open(log_path, 'a', encoding='utf-8') as lf:
            lf.write(f"_extract start: app_path={app_path}\n")
            for p in possible_fonts:
                lf.write(f"check fonts candidate: {p} exists={p.exists()}\n")
            # pick the first existing fonts dir
            for p in possible_fonts:
                if p.exists() and p.is_dir():
                    fonts_dir = p
                    break
            if not fonts_dir:
                lf.write("no fonts dir found in candidates, aborting extract\n")
                return None

        tmp_dir = Path(tempfile.mkdtemp(prefix="screenrec_fonts_"))
        copied = []
        for ttf in sorted(fonts_dir.glob('*.ttf')):
            try:
                dest = tmp_dir / ttf.name
                shutil.copy2(str(ttf), str(dest))
                copied.append(str(dest))
            except Exception:
                try:
                    with open(str(ttf), 'rb') as fr, open(str(dest), 'wb') as fw:
                        fw.write(fr.read())
                    copied.append(str(dest))
                except Exception as e:
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"复制字体失败: {ttf} -> {dest}: {e}\n")

        with open(log_path, 'a', encoding='utf-8') as lf:
            lf.write(f"selected_fonts_dir: {fonts_dir}\n")
            lf.write(f"copied_fonts: {copied}\n")

        # 在 Windows 上注册字体为进程私有（FR_PRIVATE）
        registered = []
        if platform.system() == 'Windows':
            try:
                import ctypes
                FR_PRIVATE = 0x10
                for f in sorted(tmp_dir.glob('*.ttf')):
                    try:
                        path_w = str(f.resolve())
                        res = ctypes.windll.gdi32.AddFontResourceExW(path_w, FR_PRIVATE, 0)
                        registered.append((path_w, int(res)))
                    except Exception as e:
                        with open(log_path, 'a', encoding='utf-8') as lf:
                            lf.write(f"AddFontResourceExW 失败: {f}: {e}\n")
            except Exception as e:
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"注册字体失败: {e}\n")

        # 广播字体更改消息，提示系统/应用刷新字体列表
        try:
            if platform.system() == 'Windows':
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_FONTCHANGE = 0x001D
                SMTO_ABORTIFHUNG = 0x0002
                res = ctypes.c_ulong()
                ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, ctypes.byref(res))
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"Broadcasted WM_FONTCHANGE, result={res.value}\n")
        except Exception as e:
            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(f"广播 WM_FONTCHANGE 失败: {e}\n")

        with open(log_path, 'a', encoding='utf-8') as lf:
            lf.write(f"registered: {registered}\n")

        # 尝试刷新并记录 Tk 可见的字体家族（如果 tkinter 已导入）
        try:
            import importlib
            if 'tkinter' in sys.modules:
                try:
                    import tkinter.font as _tkfont
                    fams = list(_tkfont.families())
                    # write a short preview and any matches to the log
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"tk_families_count: {len(fams)}\n")
                        lf.write('tk_families_preview: ' + ','.join(fams[:200]) + '\n')
                        matches = [f for f in fams if 'noto' in f.lower() or 'noto' in (' '.join([p.name for p in Path(f).suffixes]) if False else '')]
                        lf.write(f"tk_families_matches_noto: {matches}\n")
                except Exception as e:
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"读取 tk font families 失败: {e}\n")
        except Exception:
            pass

        return tmp_dir
    except Exception as e:
        with open(log_path, 'a', encoding='utf-8') as lf:
            lf.write(f"_extract_and_register_embedded_fonts 错误: {e}\n")
        print(f"_extract_and_register_embedded_fonts 错误: {e}")
        return None

# 默认使用完整版本（包含键盘鼠标监听）
# 如果完整版本导入失败，回退到基础版本
try:
    # 优先尝试导入完整版本（包含键盘鼠标监听）
    try:
        from luping.recorder import ScreenRecorder
        print("✓ 使用完整 recorder（包含键盘鼠标监听）")
        HAS_FULL_RECORDER = True
    except Exception as e:
        print(f"⚠️ 完整 recorder 导入失败: {e}")
        # 回退到基础版本
        from luping.recorder_no_pynput import ScreenRecorder
        print("⚠️ 回退到基础 recorder（仅录制屏幕）")
        HAS_FULL_RECORDER = False
except ImportError as e:
    print(f"✗ 错误: 无法导入 recorder 模块: {e}")
    import traceback
    traceback.print_exc()
    ScreenRecorder = None
    HAS_FULL_RECORDER = False


class RecorderGUI:
    """录屏软件GUI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("录屏软件 - 屏幕、键盘、鼠标操作录制")
        # 使用更宽的默认窗口，避免输出路径被截断；允许用户按需调整
        # enlarge default window so controls are visible on smaller screens
        self.root.geometry("900x600")
        self.root.resizable(True, True)

        # 设置跨平台默认字体：先查询系统可用字体家族，再从优先列表中选择第一个可用项
        # 如果打包时随应用携带了 fonts 目录，优先注册这些字体（Windows 下使用 AddFontResourceEx）
        try:
            fonts_dir = Path(application_path) / 'fonts'
            found_fonts = []
            if fonts_dir.exists() and fonts_dir.is_dir():
                for ttf in sorted(fonts_dir.glob('*.ttf')):
                    found_fonts.append(str(ttf))
                print(f"Embedded fonts found: {found_fonts}")
                # 尝试注册每个字体并记录返回值
                for ttf in sorted(fonts_dir.glob('*.ttf')):
                    try:
                        if platform.system() == 'Windows':
                            import ctypes
                            FR_PRIVATE = 0x10
                            path_w = str(ttf.absolute())
                            try:
                                res = ctypes.windll.gdi32.AddFontResourceExW(path_w, FR_PRIVATE, 0)
                                print(f"AddFontResourceExW({path_w}) => {res}")
                            except Exception as e:
                                print(f"AddFontResourceExW failed for {path_w}: {e}")
                        else:
                            print(f"Found embedded font (not registered on non-Windows): {ttf}")
                    except Exception as e:
                        print(f"无法注册嵌入字体 {ttf}: {e}")
                # 在注册后，强制刷新 Tk 字体家族列表并记录是否出现嵌入字体家族
                try:
                    refreshed = list(tkfont.families())
                    print(f"Refreshed font families count: {len(refreshed)}")
                    # detect likely embedded family names such as 'Noto'
                    embedded_family = None
                    for fam in refreshed:
                        if 'noto' in fam.lower() or any(p.lower() in fam.lower() for p in ['noto sans','noto']):
                            embedded_family = fam
                            break
                    if embedded_family:
                        print(f"Detected embedded font family after registration: {embedded_family}")
                        # force-configure Tk default fonts to use embedded family
                        try:
                            for named in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
                                try:
                                    f = tkfont.nametofont(named)
                                    f.configure(family=embedded_family)
                                except Exception:
                                    pass
                            # record chosen family to use later
                            self._embedded_font_family = embedded_family
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error refreshing tk font families: {e}")
            else:
                print(f"No embedded fonts directory at: {fonts_dir}")
        except Exception as e:
            print(f"Error while processing embedded fonts: {e}")

        try:
            families = list(tkfont.families())
            # store available families for UI selector
            self._available_families = families
            # 如果应用随包携带字体，优先选用其中包含的字体（例如 Noto）
            embedded_preferred = []
            try:
                fonts_dir = Path(application_path) / 'fonts'
                if fonts_dir.exists():
                    # look for likely family names from ttf filenames (simple heuristic)
                    for ttf in fonts_dir.glob('*.ttf'):
                        name = ttf.stem
                        # normalize hyphens/underscores
                        name_normal = name.replace('-', ' ').replace('_', ' ')
                        embedded_preferred.append(name_normal)
            except Exception:
                pass
            preferred_list = [
                "Microsoft YaHei", "Segoe UI", "Arial", "Tahoma",
                "SimHei", "PingFang SC", "Helvetica", "Noto Sans"
            ]
            chosen = None
            # 1) prefer embedded font family names if present
            for en in embedded_preferred:
                for f in families:
                    if en.lower() in f.lower() or f.lower() in en.lower():
                        chosen = f
                        break
                if chosen:
                    break

            # 2) otherwise prefer known system fonts
            if not chosen:
                for f in preferred_list:
                    if f in families:
                        chosen = f
                        break

            # Prefer 新宋体 (NSimSun) first, then other common Chinese fonts
            try:
                found = None
                chinese_priority = ['新宋体', 'nsimsun', 'simsun', 'simhei', '黑体', 'microsoft yahei', '微软雅黑', 'yahei']
                for cand in chinese_priority:
                    for fam in families:
                        try:
                            if cand.lower() in fam.lower() or cand in fam:
                                found = fam
                                break
                        except Exception:
                            continue
                    if found:
                        break
                if found:
                    chosen = found
            except Exception:
                pass

            if not chosen:
                chosen = families[0] if families else "Arial"

            # 获取系统/显示缩放（用于调整默认字号）
            try:
                tmp_root = tk.Tk()
                tmp_root.withdraw()
                scaling_val = float(tmp_root.tk.call('tk', 'scaling') or 1.0)
                tmp_root.destroy()
            except Exception:
                scaling_val = 1.0

            base_size = 10 if platform.system() == 'Windows' else 11
            chosen_size = max(8, int(round(base_size * (scaling_val or 1.0))))
            self.root.option_add("*Font", (chosen, chosen_size))
            self._ui_font_family = chosen

            # Create shared Font objects for consistent updates later
            try:
                self.font_ui = tkfont.Font(family=chosen, size=chosen_size)
                # Do not force bold — keep normal weight to avoid overly heavy appearance
                self.font_title = tkfont.Font(family=chosen, size=20, weight='normal')
                self.font_button = tkfont.Font(family=chosen, size=14, weight='normal')
                self.font_status = tkfont.Font(family=chosen, size=12)
                self.font_small = tkfont.Font(family=chosen, size=9)
                # store base sizes to avoid cumulative adjustments on repeated applies
                self._base_font_size = chosen_size
                self._title_size = 20
                self._button_size = 14
                self._status_size = 12
                self._small_size = 9
            except Exception:
                # fallback to None; widgets will use tuple-based fonts
                self.font_ui = None
                self.font_title = None
                self.font_button = None
                self.font_status = None
                self.font_small = None

            # 强制配置 Tk 的命名字体，确保所有内置小部件都使用同一个家族和大小
            try:
                for named in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
                    try:
                        f = tkfont.nametofont(named)
                        f.configure(family=chosen, size=chosen_size)
                    except Exception:
                        # 如果命名字体不存在，忽略
                        pass
                # Also ensure our shared font objects reflect the chosen family/size
                try:
                    if self.font_ui:
                        self.font_ui.configure(family=chosen, size=chosen_size, weight='normal')
                    if self.font_title:
                        self.font_title.configure(family=chosen, weight='normal')
                    if self.font_button:
                        self.font_button.configure(family=chosen, weight='normal')
                    if self.font_status:
                        self.font_status.configure(family=chosen, weight='normal')
                    if self.font_small:
                        self.font_small.configure(family=chosen, weight='normal')
                except Exception:
                    pass
            except Exception:
                pass

            # 将字体信息写入调试文件，便于打包后查看
            try:
                debug_path = Path(application_path) / 'font_debug.txt'
                with open(debug_path, 'w', encoding='utf-8') as df:
                    df.write(f"chosen_font: {chosen}\n")
                    df.write(f"available_families_count: {len(families)}\n")
                    df.write('families_preview: ' + ','.join(families[:200]) + '\n')
                print(f"字体诊断已写入: {debug_path}")
            except Exception:
                pass
        except Exception as e:
            print(f"设置默认字体时出错: {e}")
            self._ui_font_family = None
        # 记录更多运行时字体/Tk 信息，便于打包后分析
        try:
            try:
                # 在这里 root 可能尚未完全创建样式；如果有 root 对象则使用它
                tkver = tkfont.TkVersion
                tclver = tkfont.TclVersion
            except Exception:
                tkver = getattr(tk, 'TkVersion', 'unknown')
                tclver = getattr(tk, 'TclVersion', 'unknown')

            try:
                default_font = tkfont.nametofont('TkDefaultFont').actual()
            except Exception:
                default_font = {}

            try:
                menu_font = tkfont.nametofont('TkMenuFont').actual()
            except Exception:
                menu_font = {}

            # screen metrics
            try:
                # If root exists, use it; otherwise create a temporary one
                tmp_root = None
                if 'root' in locals() and isinstance(self.root, tk.Tk):
                    r = self.root
                else:
                    tmp_root = tk.Tk()
                    r = tmp_root
                scaling = r.tk.call('tk', 'scaling')
                screen_w = r.winfo_screenwidth()
                screen_h = r.winfo_screenheight()
                screen_mm_w = r.winfo_screenmmwidth()
                screen_mm_h = r.winfo_screenmmheight()
                if tmp_root:
                    tmp_root.destroy()
            except Exception:
                scaling = None
                screen_w = screen_h = screen_mm_w = screen_mm_h = None

            # Append details to debug file
            try:
                debug_path = Path(application_path) / 'font_debug.txt'
                with open(debug_path, 'a', encoding='utf-8') as df:
                    df.write(f"tk_version: {tkver}\n")
                    df.write(f"tcl_version: {tclver}\n")
                    df.write(f"default_font_actual: {default_font}\n")
                    df.write(f"menu_font_actual: {menu_font}\n")
                    df.write(f"scaling: {scaling}\n")
                    df.write(f"screen_pixels: {screen_w}x{screen_h}\n")
                    df.write(f"screen_mm: {screen_mm_w}x{screen_mm_h}\n")
                print(f"更多字体/Tk 信息追加到: {debug_path}")
            except Exception:
                pass
        except Exception:
            pass
        
        # 检查是否有完整 recorder
        try:
            self.has_full_recorder = HAS_FULL_RECORDER
        except NameError:
            self.has_full_recorder = False
        
        # 默认启用键盘鼠标监听（如果完整 recorder 可用）
        self.use_input_listeners = self.has_full_recorder
        print(f"GUI 初始化: has_full_recorder = {self.has_full_recorder}, use_input_listeners = {self.use_input_listeners}")
        # 之前已在上面设置为可调整，这里保持兼容
        
        # 设置工作目录
        try:
            # 在打包的应用中，使用用户目录下的 recordings 文件夹（避免权限问题）
            if getattr(sys, 'frozen', False):
                # Windows: 使用用户目录下的 recordings 文件夹
                # macOS: 使用应用包内的 Resources 目录
                if platform.system() == 'Windows':
                    # Windows 上使用用户目录，避免权限问题
                    recordings_dir = Path.home() / "ScreenRecorder" / "recordings"
                else:
                    # macOS 上使用应用包内的 Resources 目录
                    app_resources = Path(sys.executable).parent.parent / "Resources"
                    recordings_dir = app_resources / "recordings"
            else:
                recordings_dir = Path("recordings")
            
            # 确保目录存在
            recordings_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建录制器（延迟初始化 mss，避免启动时崩溃）
            if ScreenRecorder is None:
                raise RuntimeError("ScreenRecorder 模块未正确加载")
            
            # 如果完整 recorder 可用且需要启用监听，直接使用完整 recorder
            if self.use_input_listeners and self.has_full_recorder:
                print("使用完整 recorder（包含键盘鼠标监听）")
                from luping.recorder import ScreenRecorder as FullScreenRecorder
                self.recorder = FullScreenRecorder(output_dir=str(recordings_dir))
            else:
                print(f"使用基础 recorder（use_input_listeners={self.use_input_listeners}, has_full_recorder={self.has_full_recorder}）")
                self.recorder = ScreenRecorder(output_dir=str(recordings_dir))
            # 优先使用输出目录中的 fonts（如果用户把字体放在输出目录下的 fonts/ 中）
            try:
                # call extraction/registration on recordings_dir so fonts placed there get registered
                tmp_fonts_out = _extract_and_register_embedded_fonts(recordings_dir)
                if tmp_fonts_out:
                    print(f"已从输出目录提取并注册嵌入字体: {tmp_fonts_out}")
            except Exception as e:
                print(f"从输出目录注册字体时出错: {e}")
        except Exception as e:
            import traceback
            error_msg = f"初始化录制器失败: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)  # 打印到控制台
            try:
                messagebox.showerror("错误", f"初始化录制器失败: {str(e)}\n\n请查看控制台获取详细信息")
            except:
                pass
            self.recorder = None
        
        # 创建UI
        self._create_ui()

        # 自动应用默认 UI 字体（静默），确保启动时控件使用选定的默认字体
        try:
            # Try to apply immediately (widgets exist after _create_ui)
            try:
                self._apply_font_from_selector(show_message=False)
            except Exception:
                pass
            # Also schedule a shortly-delayed apply in case some widgets initialize slightly later
            try:
                self.root.after(100, lambda: self._apply_font_from_selector(show_message=False))
            except Exception:
                pass
        except Exception:
            pass

        # 延迟应用嵌入字体（有时在 Tk 初始化后字体家族才会刷新）
        try:
            # schedule a delayed attempt to detect and apply embedded fonts
            self.root.after(500, self._apply_embedded_font_later)
        except Exception:
            pass

        # 更新状态
        self._update_status()
    
    def _create_ui(self):
        """创建用户界面"""
        # 标题
        title_font = self.font_title if getattr(self, 'font_title', None) else (self._ui_font_family or "Arial", 20)
        title_label = tk.Label(
            self.root,
            text="录屏软件",
            font=title_font,
            pady=20
        )
        title_label.pack()

        # 显示当前使用的字体（用于诊断打包后字体回退问题）
        # (removed) small font-info label under title per user request

        # quick font selector removed (user requested)
        
        # 状态显示
        self.status_label = tk.Label(
            self.root,
            text="状态: 未录制",
            font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 12),
            fg="gray"
        )
        self.status_label.pack(pady=10)
        
        # 监听状态显示
        self.listener_status_label = tk.Label(
            self.root,
            text="键盘鼠标监听: 未启用",
            font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 9),
            fg="orange"
        )
        self.listener_status_label.pack(pady=2)
        
        # 录制时间显示
        self.time_label = tk.Label(
            self.root,
            text="录制时长: 00:00:00",
            font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 10),
            fg="blue"
        )
        self.time_label.pack()
        
        # 按钮框架
        button_frame = tk.Frame(self.root, pady=30)
        button_frame.pack()
        
        # 开始录制按钮
        self.start_button = tk.Button(
            button_frame,
            text="开始录制",
            command=self.start_recording,
            bg="#4CAF50",
            fg="white",
            font=self.font_button if getattr(self, 'font_button', None) else ("Arial", 14),
            width=15,
            height=2,
            relief=tk.RAISED,
            cursor="hand2"
        )
        self.start_button.pack(side=tk.LEFT, padx=10)
        
        # 停止录制按钮
        self.stop_button = tk.Button(
            button_frame,
            text="停止录制",
            command=self.stop_recording,
            bg="#f44336",
            fg="white",
            font=self.font_button if getattr(self, 'font_button', None) else ("Arial", 14),
            width=15,
            height=2,
            relief=tk.RAISED,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)
        
        # 输出目录显示
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=20, fill=tk.X, padx=20)
        
        tk.Label(
            info_frame,
            text="输出目录:",
            font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 10)
        ).pack(anchor=tk.W)
        
        output_dir_text = str(Path(self.recorder.output_dir).absolute()) if self.recorder else "未初始化"
        # 使用 StringVar 以便动态更新/复制，并扩大 wraplength 以适应更长路径
        self._output_var = tk.StringVar(value=output_dir_text)
        self.output_label = tk.Label(
            info_frame,
            textvariable=self._output_var,
            fg="blue",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=600,
            relief=tk.SUNKEN,
            bd=1
        )
        self.output_label.pack(anchor=tk.W, fill=tk.X)
        # 允许点击打开输出目录并右键复制路径
        try:
            self.output_label.bind("<Button-1>", lambda e: self._open_output_dir())
        except Exception:
            pass

        # 字体选择器：列出若干可用字体供用户选择并应用
        selector_frame = tk.Frame(self.root)
        selector_frame.pack(pady=6, fill=tk.X, padx=20)

        tk.Label(selector_frame, text="选择字体:", font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 10)).pack(side=tk.LEFT)
        fams = getattr(self, '_available_families', []) or []
        # Put likely embedded families (containing 'noto') first
        try:
            sorted_fams = sorted(fams, key=lambda f: (0 if 'noto' in f.lower() else 1, f.lower()))
        except Exception:
            sorted_fams = list(fams)

        # Default selection falls back to current UI family or first available
        default_choice = self._ui_font_family or (sorted_fams[0] if sorted_fams else 'Arial')
        self._font_var = tk.StringVar(value=default_choice)

        # Try to create a Combobox; if ttk not available or values empty, fall back to Entry
        font_combo_widget = None
        if sorted_fams:
            try:
                font_combo_widget = ttk.Combobox(selector_frame, values=sorted_fams, textvariable=self._font_var, state='readonly', width=40)
                font_combo_widget.pack(side=tk.LEFT, padx=6)
            except Exception:
                font_combo_widget = None

        if font_combo_widget is None:
            # fallback - show an Entry so user can still type a family name
            try:
                font_combo_widget = tk.Entry(selector_frame, textvariable=self._font_var, width=40)
                font_combo_widget.pack(side=tk.LEFT, padx=6)
            except Exception:
                # as a last resort, place a label indicating selector unavailable
                try:
                    tk.Label(selector_frame, text="(字体选择器不可用)", fg="gray").pack(side=tk.LEFT, padx=6)
                except Exception:
                    pass

        # Apply button (always visible)
        try:
            apply_btn = tk.Button(selector_frame, text="应用字体", command=self._apply_font_from_selector, font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 9))
            apply_btn.pack(side=tk.LEFT, padx=6)
        except Exception:
            pass
        # Add a visible button to list available fonts in a dialog (helps users find the selector)
        try:
            list_btn = tk.Button(selector_frame, text="显示字体列表", command=self._show_font_list, font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 9))
            list_btn.pack(side=tk.LEFT, padx=6)
        except Exception:
            pass
        
        # 更改输出目录按钮
        change_dir_button = tk.Button(
            self.root,
            text="更改输出目录",
            command=self.change_output_dir,
            font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 10),
            cursor="hand2"
        )
        change_dir_button.pack(pady=10)

        # 打开输出目录按钮，便于用户快速访问（尤其是路径过长时）
        open_dir_button = tk.Button(
            self.root,
            text="打开输出目录",
            command=self._open_output_dir,
            font=self.font_status if getattr(self, 'font_status', None) else ("Arial", 10),
            cursor="hand2"
        )
        open_dir_button.pack(pady=2)
        
        # 显示监听状态（不再需要复选框，默认启用）
        if self.has_full_recorder:
            listener_info = tk.Label(
                self.root,
                text="✓ 键盘和鼠标事件记录已启用（需要辅助功能权限）",
                font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 9),
                fg="green"
            )
            listener_info.pack(pady=5)
        else:
            listener_info = tk.Label(
                self.root,
                text="⚠️ 键盘鼠标事件记录功能不可用（仅录制屏幕）",
                font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 9),
                fg="orange"
            )
            listener_info.pack(pady=5)
        
        # 说明文字
        info_text = tk.Label(
            self.root,
            text="提示: 录制文件将保存在输出目录中，包含视频文件和操作事件JSON文件",
            font=self.font_small if getattr(self, 'font_small', None) else ("Arial", 8),
            fg="gray",
            wraplength=450
        )
        info_text.pack(pady=10)

        # Debug: record that UI creation reached this point and whether key widgets exist
        try:
            debug_path = Path(application_path) / 'font_debug.txt'
            with open(debug_path, 'a', encoding='utf-8') as df:
                df.write(f"ui_created: font_label_exists={hasattr(self, 'font_label')}, output_label_exists={hasattr(self, 'output_label')}, selector_exists={True if hasattr(self, '_font_var') else False}\n")
        except Exception:
            pass

    def _apply_embedded_font_later(self):
        """在 Tk 初始化完成后延迟运行，重试检测嵌入字体家族并应用。
        采用多次重试策略（每次间隔 500ms，最多 6 次），并会更新共享的 tkfont.Font 对象。
        日志写入 `font_register.log` 与 `font_debug.txt`。
        """
        try:
            internal_dir = Path(application_path) / '_internal'
            if internal_dir.exists() and internal_dir.is_dir():
                log_path = internal_dir / 'font_register.log'
            else:
                log_path = Path(application_path) / 'font_register.log'

            max_attempts = 6
            attempt = getattr(self, '_font_apply_attempt', 1)

            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(f"_apply_embedded_font_later attempt={attempt}\n")

            try:
                fams = list(tkfont.families())
            except Exception as e:
                fams = []
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"tkfont.families() 失败: {e}\n")

            embedded_family = None
            for fam in fams:
                if 'noto' in fam.lower() or 'noto sans' in fam.lower():
                    embedded_family = fam
                    break

            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(f"delayed_families_count: {len(fams)}\n")
                lf.write(f"delayed_detected_embedded_family: {embedded_family}\n")

            if embedded_family:
                try:
                    # apply to named fonts
                    for named in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
                        try:
                            f = tkfont.nametofont(named)
                            # prefer normal weight when applying embedded fonts
                            try:
                                f.configure(family=embedded_family, weight='normal')
                            except Exception:
                                f.configure(family=embedded_family)
                        except Exception:
                            pass
                    # also set option add for new widgets
                    try:
                        default_size = tkfont.nametofont('TkDefaultFont').cget('size')
                        self.root.option_add('*Font', (embedded_family, default_size))
                    except Exception:
                        pass

                    # update shared Font objects if any
                    try:
                        if getattr(self, 'font_ui', None):
                            try:
                                self.font_ui.configure(family=embedded_family, weight='normal')
                            except Exception:
                                self.font_ui.configure(family=embedded_family)
                        if getattr(self, 'font_title', None):
                            try:
                                self.font_title.configure(family=embedded_family, weight='normal')
                            except Exception:
                                self.font_title.configure(family=embedded_family)
                        if getattr(self, 'font_button', None):
                            try:
                                self.font_button.configure(family=embedded_family, weight='normal')
                            except Exception:
                                self.font_button.configure(family=embedded_family)
                        if getattr(self, 'font_status', None):
                            try:
                                self.font_status.configure(family=embedded_family, weight='normal')
                            except Exception:
                                self.font_status.configure(family=embedded_family)
                        if getattr(self, 'font_small', None):
                            try:
                                self.font_small.configure(family=embedded_family, weight='normal')
                            except Exception:
                                self.font_small.configure(family=embedded_family)
                    except Exception:
                        pass

                    # update visible label if present
                    try:
                        if hasattr(self, 'font_label') and self.font_label:
                            self.font_label.config(text=f"字体: {embedded_family}")
                    except Exception:
                        pass

                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"applied_embedded_family: {embedded_family}\n")
                    try:
                        # Also record the final applied family as chosen_font in font_debug.txt for clarity
                        debug_path = Path(application_path) / 'font_debug.txt'
                        with open(debug_path, 'a', encoding='utf-8') as df:
                            df.write(f"chosen_font: {embedded_family} (applied)\n")
                    except Exception:
                        pass
                except Exception as e:
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write(f"apply_embedded_family 失败: {e}\n")
            else:
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"未检测到嵌入字体家族 (attempt {attempt})\n")
                # schedule retry
                if attempt < max_attempts:
                    self._font_apply_attempt = attempt + 1
                    try:
                        self.root.after(500, self._apply_embedded_font_later)
                        with open(log_path, 'a', encoding='utf-8') as lf:
                            lf.write(f"scheduled next attempt={self._font_apply_attempt}\n")
                    except Exception as e:
                        with open(log_path, 'a', encoding='utf-8') as lf:
                            lf.write(f"调度下一次尝试失败: {e}\n")
                else:
                    with open(log_path, 'a', encoding='utf-8') as lf:
                        lf.write("嵌入字体检测达到最大重试次数，放弃\n")

            # also append to font_debug.txt for visibility
            try:
                debug_path = Path(application_path) / 'font_debug.txt'
                with open(debug_path, 'a', encoding='utf-8') as df:
                    df.write(f"delayed_embedded_family: {embedded_family}\n")
            except Exception:
                pass
        except Exception as e:
            try:
                with open(Path(application_path) / 'font_register.log', 'a', encoding='utf-8') as lf:
                    lf.write(f"_apply_embedded_font_later 总体失败: {e}\n")
            except Exception:
                pass

    def _apply_font_from_selector(self, show_message=True):
        """Apply the font family selected in the Combobox/Entry to the whole UI and log the action.

        Args:
            show_message (bool): if True, show a messagebox after applying; set False for silent startup apply.
        """
        try:
            chosen = None
            try:
                chosen = self._font_var.get()
            except Exception:
                pass

            if not chosen:
                try:
                    if show_message:
                        messagebox.showwarning("警告", "未选择字体")
                except Exception:
                    pass
                return

            # 1) Apply to named Tk fonts
            try:
                for named in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
                    try:
                        f = tkfont.nametofont(named)
                        f.configure(family=chosen, weight='normal')
                    except Exception:
                        pass
            except Exception:
                pass

            # 2) Update our shared Font objects
            try:
                if getattr(self, 'font_ui', None):
                    try:
                        self.font_ui.configure(family=chosen, weight='normal')
                    except Exception:
                        self.font_ui.configure(family=chosen)
                if getattr(self, 'font_title', None):
                    try:
                        self.font_title.configure(family=chosen, weight='normal')
                    except Exception:
                        self.font_title.configure(family=chosen)
                if getattr(self, 'font_button', None):
                    try:
                        self.font_button.configure(family=chosen, weight='normal')
                    except Exception:
                        self.font_button.configure(family=chosen)
                if getattr(self, 'font_status', None):
                    try:
                        self.font_status.configure(family=chosen, weight='normal')
                    except Exception:
                        self.font_status.configure(family=chosen)
                if getattr(self, 'font_small', None):
                    try:
                        self.font_small.configure(family=chosen, weight='normal')
                    except Exception:
                        self.font_small.configure(family=chosen)
            except Exception:
                pass

            # update visible label if present and remember the family
            try:
                if hasattr(self, 'font_label') and self.font_label:
                    self.font_label.config(text=f"字体: {chosen}")
            except Exception:
                pass
            self._ui_font_family = chosen

            # 3) Try non-destructive propagation: option database, ttk styles, recursive configure
            try:
                try:
                    if getattr(self, 'font_button', None):
                        try:
                            self.root.option_add('*Button.Font', self.font_button)
                        except Exception:
                            pass
                    if getattr(self, 'font_ui', None):
                        try:
                            self.root.option_add('*Label.Font', self.font_ui)
                            self.root.option_add('*Entry.Font', self.font_ui)
                            self.root.option_add('*Text.Font', self.font_ui)
                        except Exception:
                            pass
                    try:
                        style = ttk.Style()
                        if getattr(self, 'font_button', None):
                            try:
                                style.configure('TButton', font=self.font_button)
                            except Exception:
                                pass
                        if getattr(self, 'font_ui', None):
                            try:
                                style.configure('TLabel', font=self.font_ui)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

                # try to reconfigure known widgets
                widget_map = [
                    'start_button', 'stop_button', 'change_dir_button', 'open_dir_button',
                    'status_label', 'listener_status_label', 'time_label', 'font_label', 'output_label'
                ]
                for name in widget_map:
                    try:
                        w = getattr(self, name, None)
                        if w is None:
                            continue
                        if name in ('start_button', 'stop_button') and getattr(self, 'font_button', None):
                            try:
                                w.configure(font=self.font_button)
                            except Exception:
                                pass
                        elif name in ('status_label', 'time_label') and getattr(self, 'font_status', None):
                            try:
                                w.configure(font=self.font_status)
                            except Exception:
                                pass
                        elif name in ('listener_status_label',) and getattr(self, 'font_small', None):
                            try:
                                w.configure(font=self.font_small)
                            except Exception:
                                pass
                        elif name in ('font_label','output_label') and getattr(self, 'font_small', None):
                            try:
                                w.configure(font=self.font_small)
                            except Exception:
                                pass
                        else:
                            try:
                                w.configure(font=self.font_ui)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            # 4) If critical widgets (start/stop) still show the old font, recreate them as a robust fallback
            try:
                def _font_matches(widget, family):
                    try:
                        actual = tkfont.Font(font=widget.cget('font')).actual()
                        return actual.get('family', '').lower() == family.lower()
                    except Exception:
                        return False

                need_recreate = False
                try:
                    sb = getattr(self, 'start_button', None)
                    st = getattr(self, 'stop_button', None)
                    if sb is not None and not _font_matches(sb, chosen):
                        need_recreate = True
                    if st is not None and not _font_matches(st, chosen):
                        need_recreate = True
                except Exception:
                    need_recreate = False

                if need_recreate:
                    try:
                        # recreate start_button
                        for name in ('start_button', 'stop_button'):
                            w = getattr(self, name, None)
                            if w is None:
                                continue
                            parent = w.master if hasattr(w, 'master') else None
                            # capture pack/grid/place info (support pack commonly used)
                            try:
                                pack_info = w.pack_info()
                            except Exception:
                                pack_info = None
                            try:
                                grid_info = w.grid_info()
                            except Exception:
                                grid_info = None
                            try:
                                place_info = w.place_info()
                            except Exception:
                                place_info = None

                            # capture key attributes
                            try:
                                text = w.cget('text')
                            except Exception:
                                text = ''
                            try:
                                cmd = w.cget('command') if 'command' in w.keys() else None
                            except Exception:
                                cmd = None
                            try:
                                state = w.cget('state')
                            except Exception:
                                state = None

                            # destroy old widget
                            try:
                                w.destroy()
                            except Exception:
                                pass

                            # recreate with same parent and properties
                            try:
                                new = tk.Button(parent,
                                                text=text,
                                                command=getattr(self, name+'_handler', None) if False else None,
                                                bg=("#4CAF50" if name=='start_button' else "#f44336"),
                                                fg="white",
                                                font=self.font_button if getattr(self, 'font_button', None) else (chosen, self._button_size),
                                                width=15,
                                                height=2,
                                                relief=tk.RAISED,
                                                cursor="hand2")
                                # bind the original commands if possible
                                # original callbacks: start_recording, stop_recording
                                if name == 'start_button':
                                    new.config(command=self.start_recording)
                                else:
                                    new.config(command=self.stop_recording)
                                if state:
                                    try:
                                        new.config(state=state)
                                    except Exception:
                                        pass
                                # pack/grid/place as original
                                if pack_info is not None:
                                    try:
                                        new.pack(**pack_info)
                                    except Exception:
                                        pass
                                elif grid_info is not None:
                                    try:
                                        new.grid(**grid_info)
                                    except Exception:
                                        pass
                                elif place_info is not None:
                                    try:
                                        new.place(**place_info)
                                    except Exception:
                                        pass
                                # assign back to self
                                setattr(self, name, new)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            # 5) Log diagnostics for start/stop widgets
            try:
                internal_dir = Path(application_path) / '_internal'
                if internal_dir.exists() and internal_dir.is_dir():
                    log_path = internal_dir / 'font_register.log'
                else:
                    log_path = Path(application_path) / 'font_register.log'
                with open(log_path, 'a', encoding='utf-8') as lf:
                    try:
                        sb = getattr(self, 'start_button', None)
                        if sb is not None:
                            try:
                                sf = tkfont.Font(font=sb.cget('font')).actual()
                            except Exception:
                                sf = {'raw': sb.cget('font')}
                            lf.write(f"start_button_font_actual: {sf}\n")
                    except Exception:
                        pass
                    try:
                        st = getattr(self, 'stop_button', None)
                        if st is not None:
                            try:
                                sf = tkfont.Font(font=st.cget('font')).actual()
                            except Exception:
                                sf = {'raw': st.cget('font')}
                            lf.write(f"stop_button_font_actual: {sf}\n")
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if show_message:
                    messagebox.showinfo("提示", f"已应用字体: {chosen}")
            except Exception:
                pass
        except Exception as e:
            try:
                if show_message:
                    messagebox.showerror("错误", f"应用字体失败: {e}")
            except Exception:
                pass

    def _refresh_widget_fonts(self, widget=None):
        """Recursively attempt to set the shared UI font on widgets so changes become visible.
        Not all widget types accept a 'font' option; exceptions are ignored.
        """
        try:
            if widget is None:
                widget = self.root
            # prefer the central shared font object if available
            font_obj = getattr(self, 'font_ui', None)
            for child in widget.winfo_children():
                try:
                    if font_obj is not None:
                        child.configure(font=font_obj)
                    else:
                        # fallback to named TkDefaultFont
                        try:
                            child.configure(font=('TkDefaultFont',))
                        except Exception:
                            pass
                except Exception:
                    # ignore widgets that don't support 'font'
                    pass
                # recurse
                try:
                    if child.winfo_children():
                        self._refresh_widget_fonts(child)
                except Exception:
                    pass
        except Exception:
            pass

    def _show_font_list(self):
        """Show a modal window with a scrollable list of available font families for the user to pick."""
        try:
            fams = getattr(self, '_available_families', []) or []
            win = tk.Toplevel(self.root)
            win.title('可用字体列表')
            win.geometry('480x400')
            win.transient(self.root)
            lb_frame = tk.Frame(win)
            lb_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            scrollbar = tk.Scrollbar(lb_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox = tk.Listbox(lb_frame, yscrollcommand=scrollbar.set)
            for f in fams:
                listbox.insert(tk.END, f)
            listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)

            def on_apply_from_list(ev=None):
                try:
                    sel = listbox.curselection()
                    if not sel:
                        return
                    val = listbox.get(sel[0])
                    try:
                        self._font_var.set(val)
                    except Exception:
                        pass
                    self._apply_font_from_selector()
                except Exception:
                    pass

            apply_btn = tk.Button(win, text='应用所选字体', command=on_apply_from_list)
            apply_btn.pack(pady=6)
            # double-click to apply
            listbox.bind('<Double-Button-1>', on_apply_from_list)
        except Exception:
            try:
                messagebox.showerror('错误', '无法显示字体列表')
            except Exception:
                pass
    
    def start_recording(self):
        """开始录制"""
        if not self.recorder:
            messagebox.showerror("错误", "录制器未初始化")
            return
        
        try:
            # 在开始录制前，检查是否需要切换到完整 recorder
            recorder_module_name = type(self.recorder).__module__
            is_base_recorder = 'recorder_no_pynput' in recorder_module_name
            
            print(f"开始录制，当前 recorder 模块: {recorder_module_name}")
            print(f"是否基础 recorder: {is_base_recorder}")
            print(f"是否启用监听: {self.use_input_listeners}")
            print(f"完整 recorder 是否可用: {self.has_full_recorder}")
            
            if self.recorder.start_recording():
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
                self.status_label.config(text="状态: 正在录制...", fg="red")
                
                # 检查是否是完整 recorder（通过模块名）
                current_module = type(self.recorder).__module__
                is_full_recorder = 'recorder_no_pynput' not in current_module
                print(f"录制开始，recorder 模块: {current_module}")
                print(f"是否完整 recorder: {is_full_recorder}")
                
                if is_full_recorder:
                    # 等待一下，让监听器启动
                    print("等待监听器启动...")
                    self.root.after(1000, self._check_listener_status)
                else:
                    print("当前使用基础 recorder，不会记录键盘鼠标事件")
                    self.listener_status_label.config(
                        text="键盘鼠标监听: 未启用（仅录制屏幕）",
                        fg="orange"
                    )
                
                self._update_timer()
                messagebox.showinfo("提示", "录制已开始！")
            else:
                messagebox.showwarning("警告", "录制已在进行中！")
        except Exception as e:
            print(f"启动录制失败: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"启动录制失败: {str(e)}")
    
    def _check_listener_status(self):
        """检查监听器状态"""
        print("检查监听器状态...")
        
        keyboard_active = False
        mouse_active = False
        
        if hasattr(self.recorder, 'keyboard_listener'):
            keyboard_active = self.recorder.keyboard_listener is not None
            print(f"键盘监听器状态: {keyboard_active}")
        
        if hasattr(self.recorder, 'mouse_listener'):
            mouse_active = self.recorder.mouse_listener is not None
            print(f"鼠标监听器状态: {mouse_active}")
        
        if keyboard_active and mouse_active:
            self.listener_status_label.config(
                text="键盘鼠标监听: 已启用 ✓",
                fg="green"
            )
            print("✓ 键盘和鼠标监听都已启用")
        elif keyboard_active:
            self.listener_status_label.config(
                text="键盘鼠标监听: 部分启用（键盘✓，鼠标✗）",
                fg="orange"
            )
            print("⚠ 仅键盘监听启用，鼠标监听未启用")
        elif mouse_active:
            self.listener_status_label.config(
                text="键盘鼠标监听: 部分启用（键盘✗，鼠标✓）",
                fg="orange"
            )
            print("⚠ 仅鼠标监听启用，键盘监听未启用")
        else:
            self.listener_status_label.config(
                text="键盘鼠标监听: 未启用（仅录制屏幕）",
                fg="orange"
            )
            print("✗ 键盘和鼠标监听都未启用")
            print("提示: 请确保已勾选'启用键盘和鼠标事件记录'选项")
    
    def stop_recording(self):
        """停止录制"""
        if not self.recorder:
            messagebox.showerror("错误", "录制器未初始化")
            return
        
        try:
            if self.recorder.stop_recording():
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.status_label.config(text="状态: 录制已停止", fg="green")
                self.time_label.config(text="录制时长: 00:00:00")
                self.root.after_cancel(self.timer_id) if hasattr(self, 'timer_id') else None
                
                # 显示保存的文件信息
                video_path = self.recorder.video_path
                events_path = self.recorder.events_path
                
                message = f"录制已保存！\n\n"
                message += f"视频文件: {video_path.name}\n"
                message += f"事件文件: {events_path.name}\n\n"
                message += f"保存位置: {video_path.parent}"
                
                messagebox.showinfo("录制完成", message)
            else:
                messagebox.showwarning("警告", "当前没有正在进行的录制！")
        except Exception as e:
            messagebox.showerror("错误", f"停止录制失败: {str(e)}")
    
    def change_output_dir(self):
        """更改输出目录"""
        if not self.recorder:
            messagebox.showerror("错误", "录制器未初始化")
            return
        
        directory = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=str(self.recorder.output_dir)
        )
        if directory:
            self.recorder.output_dir = Path(directory)
            # 更新显示变量
            self._output_var.set(str(Path(directory).absolute()))
            messagebox.showinfo("提示", f"输出目录已更改为: {directory}")

    def _open_output_dir(self):
        """在文件管理器中打开当前输出目录（Windows: Explorer）"""
        try:
            path = Path(self.recorder.output_dir) if self.recorder else None
            if path is None:
                return
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            if platform.system() == 'Windows':
                os.startfile(str(path))
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', str(path)])
            else:
                # Linux 通用处理，尝试 xdg-open
                subprocess.Popen(['xdg-open', str(path)])
        except Exception as e:
            try:
                messagebox.showerror("错误", f"无法打开目录: {e}")
            except:
                print(f"无法打开目录: {e}")
    
    def _update_status(self):
        """更新状态显示"""
        if self.recorder and self.recorder.is_recording:
            self.status_label.config(text="状态: 正在录制...", fg="red")
        else:
            self.status_label.config(text="状态: 未录制", fg="gray")
        
        self.root.after(1000, self._update_status)
    
    def _update_timer(self):
        """更新录制时间显示"""
        if self.recorder.is_recording and self.recorder.start_time:
            elapsed = time.time() - self.recorder.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self.time_label.config(
                text=f"录制时长: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )
            self.timer_id = self.root.after(1000, self._update_timer)
        else:
            self.time_label.config(text="录制时长: 00:00:00")


def main():
    """主函数"""
    import traceback
    
    # 先创建根窗口，这样即使后面出错也能显示错误信息
    # 在创建 Tk 前尝试提取并注册嵌入字体（如果存在），这样 Tk 在初始化时能识别它们
    try:
        tmp_fonts = _extract_and_register_embedded_fonts(application_path)
        if tmp_fonts:
            print(f"嵌入字体已提取并注册（临时目录）：{tmp_fonts}")
    except Exception as e:
        print(f"提取/注册嵌入字体时出错: {e}")

    root = None
    try:
        print("初始化 tkinter...")
        root = tk.Tk()
        print("tkinter 初始化成功")
        
        print("创建 RecorderGUI...")
        app = RecorderGUI(root)
        print("RecorderGUI 创建成功")
        
        print("进入主循环...")
        root.mainloop()
        print("主循环结束")
    except KeyboardInterrupt:
        print("用户中断")
        if root:
            root.quit()
    except Exception as e:
        # 打印详细错误信息
        error_msg = f"应用启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        
        # 尝试显示错误对话框
        if root:
            try:
                import tkinter.messagebox as mb
                mb.showerror("启动错误", f"应用启动失败:\n{str(e)}\n\n请查看控制台获取详细信息")
                root.mainloop()  # 保持窗口打开以便查看错误
            except:
                pass
        else:
            # 如果连窗口都创建不了，尝试创建一个简单的错误窗口
            try:
                error_root = tk.Tk()
                error_root.title("启动错误")
                error_label = tk.Label(
                    error_root,
                    text=f"应用启动失败:\n{str(e)}\n\n详细信息请查看控制台",
                    justify=tk.LEFT,
                    padx=20,
                    pady=20
                )
                error_label.pack()
                error_root.mainloop()
            except:
                pass
        
        # 不重新抛出异常，让应用优雅退出
        sys.exit(1)


if __name__ == "__main__":
    main()
