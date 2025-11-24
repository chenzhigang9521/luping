"""
录屏软件 GUI界面
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import time

# 修复 PyInstaller 打包后的路径问题
if getattr(sys, 'frozen', False):
    # 如果是打包后的应用
    application_path = Path(sys.executable).parent
    os.chdir(application_path)
else:
    # 如果是开发环境
    application_path = Path(__file__).parent.parent

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
        self.root.geometry("500x350")
        
        # 检查是否有完整 recorder
        try:
            self.has_full_recorder = HAS_FULL_RECORDER
        except NameError:
            self.has_full_recorder = False
        
        # 默认启用键盘鼠标监听（如果完整 recorder 可用）
        self.use_input_listeners = self.has_full_recorder
        print(f"GUI 初始化: has_full_recorder = {self.has_full_recorder}, use_input_listeners = {self.use_input_listeners}")
        self.root.resizable(False, False)
        
        # 设置工作目录
        try:
            # 在打包的应用中，使用应用目录下的 recordings 文件夹
            if getattr(sys, 'frozen', False):
                # 对于 .app bundle，使用应用包内的 Resources 目录
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
        
        # 更新状态
        self._update_status()
    
    def _create_ui(self):
        """创建用户界面"""
        # 标题
        title_label = tk.Label(
            self.root,
            text="录屏软件",
            font=("Arial", 20, "bold"),
            pady=20
        )
        title_label.pack()
        
        # 状态显示
        self.status_label = tk.Label(
            self.root,
            text="状态: 未录制",
            font=("Arial", 12),
            fg="gray"
        )
        self.status_label.pack(pady=10)
        
        # 监听状态显示
        self.listener_status_label = tk.Label(
            self.root,
            text="键盘鼠标监听: 未启用",
            font=("Arial", 9),
            fg="orange"
        )
        self.listener_status_label.pack(pady=2)
        
        # 录制时间显示
        self.time_label = tk.Label(
            self.root,
            text="录制时长: 00:00:00",
            font=("Arial", 10),
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
            font=("Arial", 14, "bold"),
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
            font=("Arial", 14, "bold"),
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
            font=("Arial", 10)
        ).pack(anchor=tk.W)
        
        output_dir_text = str(Path(self.recorder.output_dir).absolute()) if self.recorder else "未初始化"
        self.output_label = tk.Label(
            info_frame,
            text=output_dir_text,
            font=("Arial", 9),
            fg="blue",
            anchor=tk.W,
            wraplength=450
        )
        self.output_label.pack(anchor=tk.W, fill=tk.X)
        
        # 更改输出目录按钮
        change_dir_button = tk.Button(
            self.root,
            text="更改输出目录",
            command=self.change_output_dir,
            font=("Arial", 10),
            cursor="hand2"
        )
        change_dir_button.pack(pady=10)
        
        # 显示监听状态（不再需要复选框，默认启用）
        if self.has_full_recorder:
            listener_info = tk.Label(
                self.root,
                text="✓ 键盘和鼠标事件记录已启用（需要辅助功能权限）",
                font=("Arial", 9),
                fg="green"
            )
            listener_info.pack(pady=5)
        else:
            listener_info = tk.Label(
                self.root,
                text="⚠️ 键盘鼠标事件记录功能不可用（仅录制屏幕）",
                font=("Arial", 9),
                fg="orange"
            )
            listener_info.pack(pady=5)
        
        # 说明文字
        info_text = tk.Label(
            self.root,
            text="提示: 录制文件将保存在输出目录中，包含视频文件和操作事件JSON文件",
            font=("Arial", 8),
            fg="gray",
            wraplength=450
        )
        info_text.pack(pady=10)
    
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
            self.output_label.config(
                text=str(Path(directory).absolute())
            )
            messagebox.showinfo("提示", f"输出目录已更改为: {directory}")
    
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
