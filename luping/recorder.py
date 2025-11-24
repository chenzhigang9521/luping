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
import subprocess
import shutil

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
        self.use_image_sequence = False  # 备用方案：保存为图像序列
        self.frame_dir = None
        self.frame_count = 0
        # FFmpeg 管道写入器相关
        self.use_ffmpeg_pipe = False
        self.ffmpeg_proc = None
        self.ffmpeg_stdin = None
        # 调试/诊断字段
        self._debug_log_path = None
        self._frames_written = 0
        self._writer_opened = False
        self._ffmpeg_stderr = None
        
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
        
        # 创建输出文件名（优先使用 MP4 格式）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_path = self.output_dir / f"recording_{timestamp}.mp4"
        self.events_path = self.output_dir / f"events_{timestamp}.json"
        
        # 确保输出目录存在且可写
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            # 测试目录是否可写
            test_file = self.output_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
            print(f"✓ 输出目录可写: {self.output_dir}")
        except Exception as e:
            raise RuntimeError(f"无法写入输出目录 {self.output_dir}: {e}")
        
        # 检查 OpenCV 版本和功能
        print(f"OpenCV 版本: {cv2.__version__}")
        print(f"准备初始化视频写入器: {self.video_path}")
        print(f"分辨率: {self.width}x{self.height}, FPS: 30")
        
        # 尝试多个编码器，按优先级顺序
        # 优先尝试 MP4 兼容的编码器
        # 增加更兼容的编码器选项
        # 优先尝试 AVI+MJPG，因为在无 ffmpeg 的环境下更可能生成可播放文件
        codecs_to_try = [
            ('MJPG', 'MJPG', '.avi'),  # Motion JPEG，AVI 格式（兼容性好）
            ('XVID', 'XVID', '.avi'),  # XVID，AVI 格式
            ('DIVX', 'DIVX', '.avi'),  # DivX，AVI 格式
            ('MP4V', 'mp4v', '.mp4'),  # 通用 MP4 编码器
            ('H264', 'H264', '.mp4'),  # H.264 编码器
            ('X264', 'X264', '.mp4'),  # X.264 编码器
            ('avc1', 'avc1', '.mp4'),  # AVC1 编码器
        ]
        
        self.video_writer = None
        last_error = None
        
        for codec_name, fourcc_code, file_ext in codecs_to_try:
            try:
                # 根据编码器调整文件扩展名
                if file_ext == '.mp4' and self.video_path.suffix != '.mp4':
                    # 如果尝试 MP4 编码器，确保文件扩展名是 .mp4
                    video_path_actual = self.video_path.with_suffix('.mp4')
                elif file_ext == '.avi' and self.video_path.suffix != '.avi':
                    # 如果尝试 AVI 编码器，使用 .avi 扩展名
                    video_path_actual = self.video_path.with_suffix('.avi')
                else:
                    video_path_actual = self.video_path
                
                fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                print(f"尝试使用 {codec_name} 编码器 (FourCC: {fourcc_code}, 格式: {file_ext})...")
                
                # 使用绝对路径
                video_path_str = str(video_path_actual.absolute())
                print(f"  视频文件路径: {video_path_str}")
                
                self.video_writer = cv2.VideoWriter(
                    video_path_str,
                    fourcc,
                    30.0,  # FPS
                    (int(self.width), int(self.height)),
                    True  # isColor=True (BGR 图像)
                )
                
                # 测试写入器是否可用
                if self.video_writer.isOpened():
                    print(f"  VideoWriter.isOpened() = True")
                    # 不依赖 VideoWriter.write() 的返回值（通常为 None）来判断是否可写。
                    # 仅通过 isOpened() 判断并记录选择的编码器与路径。
                    print(f"✓ 使用 {codec_name} 编码器初始化视频写入器成功")
                    # 更新视频路径（可能因为编码器改变了扩展名）
                    self.video_path = video_path_actual
                    # 记录写入器已打开（调试信息）
                    self._writer_opened = True
                    # 保持 video_writer 已打开以继续写帧
                    break
                else:
                    print(f"⚠️ {codec_name} 编码器初始化失败: VideoWriter.isOpened() = False")
                    if self.video_writer:
                        try:
                            self.video_writer.release()
                        except:
                            pass
                    self.video_writer = None
            except Exception as e:
                last_error = str(e)
                print(f"⚠️ {codec_name} 编码器不可用: {e}")
                import traceback
                traceback.print_exc()
                if self.video_writer:
                    try:
                        self.video_writer.release()
                    except:
                        pass
                    self.video_writer = None
                continue
        
        if self.video_writer is None or not self.video_writer.isOpened():
            # 如果所有编码器都失败，优先尝试使用系统 ffmpeg 通过管道编码
            print("⚠️ 所有 OpenCV 视频编码器不可用，尝试使用系统 ffmpeg 管道写入...")
            ffmpeg_ok = self._try_start_ffmpeg(self.video_path)
            if ffmpeg_ok:
                self.use_ffmpeg_pipe = True
                print(f"✓ 使用 FFmpeg 管道写入: {self.video_path}")
            else:
                # 回退到图像序列方案
                print("⚠️ FFmpeg 不可用或启动失败，回退到图像序列保存")
                self.video_writer = None
                self.use_image_sequence = True
                self.frame_dir = self.video_path.parent / f"{self.video_path.stem}_frames"
                self.frame_dir.mkdir(parents=True, exist_ok=True)
                self.frame_count = 0
                print(f"✓ 图像序列将保存到: {self.frame_dir}")
                print("  提示: 录制完成后，可以使用 FFmpeg 或其他工具将图像序列转换为视频")
                print("  命令示例: ffmpeg -r 30 -i frame_%06d.jpg -c:v libx264 output.mp4")
        
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

        # 初始化调试日志路径
        try:
            self._debug_log_path = self.video_path.parent / (self.video_path.stem + '.debug.txt')
            self._frames_written = 0
        except Exception:
            self._debug_log_path = None
        
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
        
        # 释放视频写入器或处理图像序列
        if self.use_image_sequence:
            print("正在完成图像序列保存...")
            try:
                if self.frame_dir and self.frame_dir.exists():
                    frame_count = len(list(self.frame_dir.glob("frame_*.jpg")))
                    print(f"✓ 图像序列已保存: {self.frame_dir}")
                    print(f"  共 {frame_count} 帧图像")
                    print(f"  提示: 可以使用 FFmpeg 转换为视频:")
                    output_video = self.video_path.parent / (self.video_path.stem + '_from_frames.mp4')
                    print(f"  ffmpeg -r 30 -i \"{self.frame_dir}/frame_%06d.jpg\" -c:v libx264 -pix_fmt yuv420p \"{output_video}\"")
            except Exception as e:
                print(f"⚠️ 处理图像序列时发生错误: {e}")
                import traceback
                traceback.print_exc()
        elif self.video_writer:
            print("正在释放视频写入器...")
            try:
                self.video_writer.release()
                print(f"✓ 视频写入器已释放")

                # 详细检查视频文件，若不可播放并且系统有 ffmpeg，则尝试转码
                ok = self._verify_video_file()
                if not ok:
                    print("⚠️ 视频文件验证未通过，尝试使用系统 ffmpeg 转码为可播放 MP4（如果可用）...")
                    try:
                        import shutil, subprocess
                        ff = shutil.which('ffmpeg')
                        if ff:
                            output_fixed = self.video_path.with_suffix('.fixed.mp4')
                            cmd = [ff, '-y', '-i', str(self.video_path), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output_fixed)]
                            print(f"运行: {' '.join(cmd)}")
                            proc = subprocess.run(cmd, capture_output=True, text=True)
                            if proc.returncode == 0 and output_fixed.exists():
                                print(f"✓ 转码成功: {output_fixed}")
                                # 替换视频路径为转码后文件
                                self.video_path = output_fixed
                                # 再次验证
                                self._verify_video_file()
                            else:
                                print(f"✗ 转码失败: {proc.stderr}")
                        else:
                            print("✗ 系统未找到 ffmpeg，无法转码")
                    except Exception as e:
                        print(f"⚠️ 转码过程中发生异常: {e}")
                        import traceback
                        traceback.print_exc()
            except Exception as e:
                print(f"⚠️ 释放视频写入器时发生错误: {e}")
                import traceback
                traceback.print_exc()
        elif self.use_ffmpeg_pipe:
            print("正在关闭 FFmpeg 管道并等待进程完成...")
            try:
                self._stop_ffmpeg()
                print(f"✓ FFmpeg 管道已关闭，输出文件: {self.video_path}")
                self._verify_video_file()
            except Exception as e:
                print(f"⚠️ 关闭 FFmpeg 管道时发生错误: {e}")
                import traceback
                traceback.print_exc()

        # 写入调试日志（如果可用）
        try:
            if self._debug_log_path:
                info_lines = [
                    f"video_path: {self.video_path}",
                    f"writer_opened: {self._writer_opened}",
                    f"use_image_sequence: {self.use_image_sequence}",
                    f"use_ffmpeg_pipe: {self.use_ffmpeg_pipe}",
                    f"frames_written: {self._frames_written}",
                ]
                if self._ffmpeg_stderr:
                    info_lines.append("ffmpeg_stderr:")
                    info_lines.append(self._ffmpeg_stderr)
                with open(self._debug_log_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(info_lines))
                print(f"✓ 调试日志已写入: {self._debug_log_path}")
        except Exception as e:
            print(f"⚠️ 写入调试日志失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 保存事件到JSON文件
        self._save_events()
        
        return True
    
    def _record_screen(self):
        """录制屏幕（在单独线程中运行）"""
        # 在录制线程中创建 mss 实例，避免将主线程的 GDI 句柄传入子线程
        try:
            sct = mss.mss()
            monitor = sct.monitors[1]
        except Exception:
            if self.sct:
                sct = self.sct
                monitor = sct.monitors[1]
            else:
                print("✗ 无法初始化屏幕捕获（mss）")
                return
        frame_count = 0
        
        print(f"开始录制屏幕: 分辨率 {self.width}x{self.height}, FPS 30")
        
        while self.is_recording:
            try:
                # 捕获屏幕
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                
                # 转换颜色空间（BGRA to BGR）
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 确保图像尺寸正确
                if img.shape[1] != self.width or img.shape[0] != self.height:
                    img = cv2.resize(img, (self.width, self.height))
                
                # 写入视频或图像序列
                if self.use_image_sequence:
                    # 备用方案：保存为图像序列
                    frame_filename = self.frame_dir / f"frame_{self.frame_count:06d}.jpg"
                    cv2.imwrite(str(frame_filename), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    frame_count += 1
                    self.frame_count = frame_count
                    if frame_count % 300 == 0:  # 每10秒打印一次
                        print(f"已保存 {frame_count} 帧图像 (约 {frame_count/30:.1f} 秒)")
                elif self.use_ffmpeg_pipe:
                    # 将原始 BGR 帧写入 FFmpeg stdin
                    try:
                        self._write_frame_ffmpeg(img)
                    except Exception as e:
                        print(f"⚠️ 写入 FFmpeg 帧异常 (帧 {frame_count}): {e}")
                    frame_count += 1
                elif self.video_writer and self.video_writer.isOpened():
                    # VideoWriter.write() 通常不返回写入结果（返回 None），
                    # 因此不依赖其返回值判断成功与否，只执行写入并统计帧数。
                    try:
                        self.video_writer.write(img)
                    except Exception as e:
                        print(f"⚠️ 警告: 写入视频帧时发生异常 (帧 {frame_count}): {e}")
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
        # 把本次录制的帧数保存到实例字段，供 stop_recording 使用
        try:
            self._frames_written = frame_count
        except Exception:
            pass
    
    def _verify_video_file(self):
        """验证视频文件是否正确生成"""
        print("\n" + "=" * 60)
        print("开始验证视频文件...")
        print("=" * 60)
        
        # 1. 检查文件是否存在
        if not self.video_path.exists():
            print("❌ 错误: 视频文件不存在")
            print(f"   预期路径: {self.video_path.absolute()}")
            return False
        
        print(f"✓ 文件存在: {self.video_path.absolute()}")
        
        # 2. 检查文件大小
        file_size = self.video_path.stat().st_size
        print(f"✓ 文件大小: {file_size:,} 字节 ({file_size / (1024*1024):.2f} MB)")
        
        if file_size == 0:
            print("❌ 错误: 视频文件大小为 0，没有写入任何数据")
            return False
        
        if file_size < 1024:
            print("⚠️ 警告: 视频文件非常小（< 1KB），可能不完整")
        
        # 3. 检查文件头（Magic Number）
        try:
            with open(self.video_path, 'rb') as f:
                header = f.read(12)
                print(f"✓ 文件头（前12字节）: {header.hex()}")
                
                # MP4 文件应该以 ftyp box 开头
                if self.video_path.suffix == '.mp4':
                    if header[:4] == b'\x00\x00\x00' or header[4:8] == b'ftyp':
                        print("✓ MP4 文件头格式正确")
                    else:
                        print("⚠️ 警告: MP4 文件头格式可能不正确")
                        print(f"   前4字节: {header[:4]}")
                        print(f"   4-8字节: {header[4:8]}")
                
                # AVI 文件应该以 RIFF 开头
                elif self.video_path.suffix == '.avi':
                    if header[:4] == b'RIFF':
                        print("✓ AVI 文件头格式正确")
                    else:
                        print("⚠️ 警告: AVI 文件头格式可能不正确")
                        print(f"   前4字节: {header[:4]}")
        except Exception as e:
            print(f"⚠️ 读取文件头时出错: {e}")
        
        # 4. 尝试用 OpenCV 读取视频文件
        print("\n尝试用 OpenCV 读取视频文件...")
        try:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                print("❌ 错误: OpenCV 无法打开视频文件")
                return False
            
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            print(f"✓ OpenCV 可以打开视频文件")
            print(f"  帧率 (FPS): {fps}")
            print(f"  总帧数: {frame_count}")
            print(f"  分辨率: {width}x{height}")
            print(f"  编码器 (FourCC): {fourcc_str} ({fourcc})")
            
            if frame_count == 0:
                print("❌ 错误: 视频文件没有帧数据")
                cap.release()
                return False
            
            # 尝试读取第一帧
            ret, frame = cap.read()
            if ret:
                print(f"✓ 可以读取第一帧，尺寸: {frame.shape}")
            else:
                print("❌ 错误: 无法读取视频帧")
                cap.release()
                return False
            
            # 尝试读取最后一帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)
            ret, frame = cap.read()
            if ret:
                print(f"✓ 可以读取最后一帧")
            else:
                print("⚠️ 警告: 无法读取最后一帧，视频可能不完整")
            
            cap.release()
            print("\n✓ 视频文件验证通过，文件应该是有效的")
            return True
            
        except Exception as e:
            print(f"❌ 验证视频文件时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("=" * 60 + "\n")

    # -------------------- FFmpeg 管道相关方法 --------------------
    def _try_start_ffmpeg(self, output_path: Path) -> bool:
        """尝试使用系统 ffmpeg 启动管道写入进程，返回是否成功"""
        try:
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                print("✗ 未在 PATH 中找到 ffmpeg 可执行文件")
                return False

            width = int(self.width)
            height = int(self.height)
            output_str = str(output_path.absolute())

            cmd = [
                ffmpeg_path,
                '-y',
                '-f', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{width}x{height}',
                '-r', '30',
                '-i', '-',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'veryfast',
                output_str
            ]

            print(f"启动 FFmpeg: {' '.join(cmd)}")
            # 在 Windows 上，ensure stdin is PIPE and use creationflags to hide console
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.ffmpeg_proc = proc
            self.ffmpeg_stdin = proc.stdin
            return True
        except Exception as e:
            print(f"✗ 无法启动 FFmpeg 进程: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _write_frame_ffmpeg(self, img: np.ndarray):
        """将单帧 BGR 图像写入 FFmpeg stdin。"""
        if self.ffmpeg_stdin is None:
            raise RuntimeError("FFmpeg stdin 未打开")
        # 确保图像为 BGR24，连续内存
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)
        if not img.flags['C_CONTIGUOUS']:
            img = np.ascontiguousarray(img)
        # 写入原始字节（BGR24）
        self.ffmpeg_stdin.write(img.tobytes())

    def _stop_ffmpeg(self):
        """关闭 FFmpeg stdin 并等待进程完成"""
        if self.ffmpeg_stdin:
            try:
                self.ffmpeg_stdin.close()
            except Exception:
                pass
            self.ffmpeg_stdin = None
        if self.ffmpeg_proc:
            try:
                # 等待 ffmpeg 退出，并捕获输出用于调试
                out, err = self.ffmpeg_proc.communicate(timeout=10)
                if out:
                    print(f"FFmpeg stdout: {out.decode(errors='ignore')}")
                if err:
                    decoded_err = err.decode(errors='ignore')
                    print(f"FFmpeg stderr: {decoded_err}")
                    # 保存 stderr 到实例字段，供外部写入调试日志
                    self._ffmpeg_stderr = decoded_err
            except subprocess.TimeoutExpired:
                try:
                    self.ffmpeg_proc.kill()
                except Exception:
                    pass
            finally:
                self.ffmpeg_proc = None
    
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
