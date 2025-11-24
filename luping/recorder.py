"""
录屏软件 - 记录屏幕、键盘和鼠标操作
"""
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue
import cv2
import mss
import numpy as np
import platform

# 延迟导入 pynput，避免在导入时就初始化导致崩溃
_keyboard = None
_mouse = None

def _get_keyboard():
    """延迟加载 keyboard 模块"""
    global _keyboard
    if _keyboard is None:
        try:
            # 使用更安全的方式导入，避免在导入时就初始化
            import importlib.util
            
            # 尝试导入 pynput.keyboard
            spec = importlib.util.find_spec("pynput.keyboard")
            if spec is None:
                raise ImportError("pynput.keyboard 模块未找到")
            
            # 动态导入模块
            keyboard_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(keyboard_module)
            _keyboard = keyboard_module
        except Exception as e:
            print(f"警告: 无法导入 keyboard 模块: {e}")
            import traceback
            traceback.print_exc()
            _keyboard = False  # 标记为不可用
    return _keyboard if _keyboard is not False else None


def _get_mouse():
    """延迟加载 mouse 模块"""
    global _mouse
    if _mouse is None:
        try:
            # 使用更安全的方式导入
            import importlib.util
            
            # 尝试导入 pynput.mouse
            spec = importlib.util.find_spec("pynput.mouse")
            if spec is None:
                raise ImportError("pynput.mouse 模块未找到")
            
            # 动态导入模块
            mouse_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mouse_module)
            _mouse = mouse_module
        except Exception as e:
            print(f"警告: 无法导入 mouse 模块: {e}")
            import traceback
            traceback.print_exc()
            _mouse = False  # 标记为不可用
    return _mouse if _mouse is not False else None


class ScreenRecorder:
    """屏幕录制器"""
    
    def __init__(self, output_dir="recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.is_recording = False
        self.recording_thread = None
        self.video_writer = None
        
        # 延迟初始化 mss，避免在导入时就初始化
        self.sct = None
        self.width = None
        self.height = None
        
        # 初始化屏幕捕获（延迟到需要时）
        try:
            self.sct = mss.mss()
            # 获取屏幕尺寸
            monitor = self.sct.monitors[1]  # 主显示器
            self.width = monitor["width"]
            self.height = monitor["height"]
        except Exception as e:
            print(f"警告: 初始化屏幕捕获失败: {e}")
            # 使用默认值
            self.width = 1920
            self.height = 1080
        
        # 事件队列
        self.events_queue = Queue()
        
        # 键盘和鼠标监听器
        self.keyboard_listener = None
        self.mouse_listener = None
        
        # 录制开始时间
        self.start_time = None
        
    def start_recording(self):
        """开始录制"""
        if self.is_recording:
            return False
        
        # 确保屏幕捕获已初始化
        if self.sct is None:
            try:
                self.sct = mss.mss()
                monitor = self.sct.monitors[1]
                self.width = monitor["width"]
                self.height = monitor["height"]
            except Exception as e:
                raise RuntimeError(f"无法初始化屏幕捕获: {e}")
            
        self.is_recording = True
        self.start_time = time.time()
        
        # 创建输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_path = self.output_dir / f"recording_{timestamp}.avi"
        self.events_path = self.output_dir / f"events_{timestamp}.json"
        
        # 初始化视频写入器
        # 尝试多个编码器，按优先级顺序
        # Windows 上推荐使用 MJPG 或 XVID
        codecs_to_try = [
            ('MJPG', 'MJPG'),  # Motion JPEG，兼容性最好，Windows 上最可靠
            ('XVID', 'XVID'),  # XVID 编码器，兼容性好
            ('DIVX', 'DIVX'),  # DivX 编码器（Windows 上常用）
            ('X264', 'X264'),  # H.264 编码器（如果可用）
            ('mp4v', 'mp4v'),  # 原始编码器（作为最后备选）
        ]
        
        print(f"准备初始化视频写入器: {self.video_path}")
        print(f"分辨率: {self.width}x{self.height}, FPS: 30")
        
        self.video_writer = None
        for codec_name, fourcc_code in codecs_to_try:
            try:
                fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                print(f"尝试使用 {codec_name} 编码器...")
                self.video_writer = cv2.VideoWriter(
                    str(self.video_path),
                    fourcc,
                    30.0,  # FPS
                    (self.width, self.height),
                    True  # isColor=True (BGR 图像)
                )
                # 测试写入器是否可用
                if self.video_writer.isOpened():
                    # 尝试写入一个测试帧来验证
                    test_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    if self.video_writer.write(test_frame):
                        print(f"✓ 使用 {codec_name} 编码器初始化视频写入器成功")
                        break
                    else:
                        print(f"⚠️ {codec_name} 编码器无法写入测试帧，尝试下一个...")
                        self.video_writer.release()
                        self.video_writer = None
                else:
                    print(f"⚠️ {codec_name} 编码器初始化失败，尝试下一个...")
                    if self.video_writer:
                        self.video_writer.release()
                    self.video_writer = None
            except Exception as e:
                print(f"⚠️ {codec_name} 编码器不可用: {e}")
                if self.video_writer:
                    try:
                        self.video_writer.release()
                    except:
                        pass
                    self.video_writer = None
                continue
        
        if self.video_writer is None or not self.video_writer.isOpened():
            raise RuntimeError("无法初始化视频写入器，所有编码器都不可用。请检查 OpenCV 是否正确安装。")
        
        # 延迟加载并启动键盘和鼠标监听
        # 在 macOS 上，pynput 的某些操作可能导致崩溃，所以完全可选
        # 使用 try-except 包裹整个监听启动过程，确保即使失败也不影响录制
        print("=" * 50)
        print("开始启动键盘和鼠标监听...")
        print("=" * 50)
        
        try:
            print("步骤 1: 加载 keyboard 模块...")
            keyboard_module = _get_keyboard()
            print(f"keyboard 模块: {keyboard_module is not None}")
            
            print("步骤 2: 加载 mouse 模块...")
            mouse_module = _get_mouse()
            print(f"mouse 模块: {mouse_module is not None}")
            
            # 启动键盘监听（如果失败，只记录警告，不阻止录制）
            if keyboard_module:
                try:
                    print("步骤 3: 创建键盘监听器...")
                    self.keyboard_listener = keyboard_module.Listener(
                        on_press=self._on_key_press,
                        on_release=self._on_key_release,
                        suppress=False
                    )
                    print("步骤 4: 启动键盘监听器...")
                    self.keyboard_listener.start()
                    print("=" * 50)
                    print("✓ 键盘监听已启动")
                    print("=" * 50)
                except Exception as e:
                    print("=" * 50)
                    print(f"✗ 警告: 无法启动键盘监听: {e}")
                    print("=" * 50)
                    import traceback
                    traceback.print_exc()
                    self.keyboard_listener = None
            else:
                print("=" * 50)
                print("✗ 警告: keyboard 模块不可用，将跳过键盘事件记录")
                print("=" * 50)
                self.keyboard_listener = None
            
            # 启动鼠标监听
            # 注意：macOS 上 pynput.mouse 可能不稳定，即使有权限也可能崩溃
            # 如果主要使用环境是 Windows，macOS 上可以跳过鼠标监听
            if mouse_module:
                # macOS 上可以选择性禁用鼠标监听，避免崩溃
                if platform.system() == 'Darwin':
                    print("步骤 5: macOS 系统检测到")
                    print("  提示: macOS 上鼠标监听可能不稳定，为安全起见跳过鼠标监听")
                    print("  提示: 应用将继续运行，仅记录键盘事件和屏幕")
                    print("=" * 50)
                    print("⚠️ macOS 上已禁用鼠标监听（避免崩溃）")
                    print("   提示: Windows 版本将正常支持鼠标监听")
                    print("=" * 50)
                    self.mouse_listener = None
                else:
                    # Windows/Linux 上正常启动鼠标监听
                    print("步骤 5: 准备启动鼠标监听器...")
                    try:
                        print("  创建鼠标监听器对象...")
                        self.mouse_listener = mouse_module.Listener(
                            on_move=self._on_mouse_move,
                            on_click=self._on_mouse_click,
                            on_scroll=self._on_mouse_scroll,
                            suppress=False
                        )
                        print("  启动鼠标监听器...")
                        self.mouse_listener.start()
                        print("=" * 50)
                        print("✓ 鼠标监听已启动")
                        print("=" * 50)
                    except Exception as e:
                        print("=" * 50)
                        print(f"✗ 警告: 无法启动鼠标监听: {e}")
                        print("=" * 50)
                        import traceback
                        traceback.print_exc()
                        self.mouse_listener = None
            else:
                print("=" * 50)
                print("✗ 警告: mouse 模块不可用，将跳过鼠标事件记录")
                print("=" * 50)
                self.mouse_listener = None
        except Exception as e:
            # 即使整个监听启动过程失败，也不影响录制
            print("=" * 50)
            print(f"✗ 严重警告: 启动输入监听时发生错误: {e}")
            print("=" * 50)
            import traceback
            traceback.print_exc()
            self.keyboard_listener = None
            self.mouse_listener = None
            print("将继续进行屏幕录制，但不会记录键盘和鼠标事件")
        
        # 启动屏幕录制线程
        self.recording_thread = threading.Thread(target=self._record_screen)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        return True
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return False
            
        self.is_recording = False
        
        # 停止监听器
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        
        # 等待录制线程结束
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        
        # 释放视频写入器
        if self.video_writer:
            print("正在释放视频写入器...")
            try:
                self.video_writer.release()
                print(f"✓ 视频写入器已释放")
                # 检查文件是否存在且大小大于0
                if self.video_path.exists():
                    file_size = self.video_path.stat().st_size
                    print(f"✓ 视频文件已保存: {self.video_path}")
                    print(f"  文件大小: {file_size / (1024*1024):.2f} MB")
                    if file_size == 0:
                        print("⚠️ 警告: 视频文件大小为 0，可能没有正确写入数据")
                else:
                    print("⚠️ 警告: 视频文件不存在")
            except Exception as e:
                print(f"⚠️ 释放视频写入器时发生错误: {e}")
                import traceback
                traceback.print_exc()
        
        # 保存事件到JSON文件
        self._save_events()
        
        return True
    
    def _record_screen(self):
        """录制屏幕（在单独线程中运行）"""
        monitor = self.sct.monitors[1]
        frame_count = 0
        
        print(f"开始录制屏幕: 分辨率 {self.width}x{self.height}, FPS 30")
        
        while self.is_recording:
            try:
                # 捕获屏幕
                screenshot = self.sct.grab(monitor)
                img = np.array(screenshot)
                
                # 转换颜色空间（BGRA to BGR）
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 确保图像尺寸正确
                if img.shape[1] != self.width or img.shape[0] != self.height:
                    img = cv2.resize(img, (self.width, self.height))
                
                # 写入视频
                if self.video_writer and self.video_writer.isOpened():
                    success = self.video_writer.write(img)
                    if not success:
                        print(f"⚠️ 警告: 写入视频帧失败 (帧 {frame_count})")
                    frame_count += 1
                    if frame_count % 300 == 0:  # 每10秒打印一次
                        print(f"已录制 {frame_count} 帧 (约 {frame_count/30:.1f} 秒)")
                else:
                    print("⚠️ 警告: 视频写入器不可用")
                    break
                
                # 控制帧率（约30fps）
                time.sleep(1/30)
            except Exception as e:
                print(f"⚠️ 录制屏幕时发生错误: {e}")
                import traceback
                traceback.print_exc()
                break
        
        print(f"录制结束，共录制 {frame_count} 帧")
    
    def _on_key_press(self, key):
        """键盘按下事件"""
        if not self.is_recording:
            return
        
        try:
            timestamp = time.time() - self.start_time
            try:
                key_name = key.char if hasattr(key, 'char') and key.char else str(key)
            except:
                key_name = str(key)
            
            event = {
                "type": "key_press",
                "key": key_name,
                "timestamp": round(timestamp, 3)
            }
            self.events_queue.put(event)
            # 调试：每10个事件打印一次
            if self.events_queue.qsize() % 10 == 0:
                print(f"已记录 {self.events_queue.qsize()} 个事件")
        except Exception as e:
            print(f"记录键盘事件时出错: {e}")
    
    def _on_key_release(self, key):
        """键盘释放事件"""
        if not self.is_recording:
            return
        
        try:
            timestamp = time.time() - self.start_time
            try:
                key_name = key.char if hasattr(key, 'char') and key.char else str(key)
            except:
                key_name = str(key)
            
            event = {
                "type": "key_release",
                "key": key_name,
                "timestamp": round(timestamp, 3)
            }
            self.events_queue.put(event)
        except Exception as e:
            print(f"记录键盘释放事件时出错: {e}")
    
    def _on_mouse_move(self, x, y):
        """鼠标移动事件"""
        if not self.is_recording:
            return
        
        try:
            # 减少鼠标移动事件的频率，避免事件过多
            current_time = time.time()
            if not hasattr(self, '_last_mouse_move_time'):
                self._last_mouse_move_time = 0
            
            # 每0.1秒记录一次鼠标移动（降低频率）
            if current_time - self._last_mouse_move_time < 0.1:
                return
            
            self._last_mouse_move_time = current_time
            timestamp = current_time - self.start_time
            
            event = {
                "type": "mouse_move",
                "x": x,
                "y": y,
                "timestamp": round(timestamp, 3)
            }
            self.events_queue.put(event)
        except Exception as e:
            print(f"记录鼠标移动事件时出错: {e}")
    
    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击事件"""
        if not self.is_recording:
            return
        
        try:
            timestamp = time.time() - self.start_time
            event = {
                "type": "mouse_click",
                "x": x,
                "y": y,
                "button": str(button),
                "pressed": pressed,
                "timestamp": round(timestamp, 3)
            }
            self.events_queue.put(event)
            print(f"记录鼠标点击: {button} {'按下' if pressed else '释放'} at ({x}, {y})")
        except Exception as e:
            print(f"记录鼠标点击事件时出错: {e}")
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """鼠标滚动事件"""
        if not self.is_recording:
            return
        
        try:
            timestamp = time.time() - self.start_time
            event = {
                "type": "mouse_scroll",
                "x": x,
                "y": y,
                "dx": dx,
                "dy": dy,
                "timestamp": round(timestamp, 3)
            }
            self.events_queue.put(event)
        except Exception as e:
            print(f"记录鼠标滚动事件时出错: {e}")
    
    def _save_events(self):
        """保存事件到JSON文件"""
        events = []
        queue_size = self.events_queue.qsize()
        print(f"保存事件: 队列中有 {queue_size} 个事件")
        
        # 检查监听器状态
        keyboard_active = self.keyboard_listener is not None
        mouse_active = self.mouse_listener is not None
        
        if not keyboard_active and not mouse_active:
            print("⚠️  警告: 键盘和鼠标监听器都未启用，events 文件将为空")
            print("   提示: 请在应用界面勾选'启用键盘和鼠标事件记录'选项")
            print("   或者: 当前使用的是基础版本（仅录制屏幕）")
            if platform.system() == 'Darwin':
                print("   注意: macOS 上已禁用鼠标监听（避免崩溃），Windows 版本将正常支持")
        
        while not self.events_queue.empty():
            events.append(self.events_queue.get())
        
        # 按时间戳排序
        events.sort(key=lambda x: x["timestamp"])
        
        print(f"实际保存了 {len(events)} 个事件到 {self.events_path}")
        
        if len(events) == 0:
            print("⚠️  事件文件为空！可能的原因：")
            print("   1. 没有勾选'启用键盘和鼠标事件记录'选项")
            if platform.system() == 'Darwin':
                print("   2. macOS 上已禁用鼠标监听（避免崩溃），仅记录键盘事件")
            else:
                print("   2. 没有授予辅助功能权限（macOS）")
            print("   3. 监听器启动失败（查看上面的错误信息）")
            print("   4. 录制期间没有进行任何键盘鼠标操作")
        
        # 保存到JSON
        try:
            with open(self.events_path, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            print(f"✓ 事件文件保存成功: {self.events_path}")
        except Exception as e:
            print(f"✗ 保存事件文件失败: {e}")
            import traceback
            traceback.print_exc()
        
        return len(events)
