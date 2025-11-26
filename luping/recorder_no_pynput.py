"""
录屏软件 - 仅录制屏幕（不包含键盘和鼠标监听）
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
import subprocess
import shutil
import sys


class ScreenRecorder:
    """屏幕录制器（仅录制屏幕，不记录键盘和鼠标）"""
    
    def __init__(self, output_dir="recordings", scale_factor=1.0, target_fps=30.0):
        """
        初始化录屏器
        
        Args:
            output_dir: 输出目录
            scale_factor: 分辨率缩放因子 (0.5 = 半分辨率, 1.0 = 原始分辨率)
            target_fps: 目标帧率 (默认30帧)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.scale_factor = max(0.25, min(1.0, scale_factor))
        self.target_fps = max(15.0, min(60.0, target_fps))
        
        self.is_recording = False
        self.recording_thread = None
        self.video_writer = None
        # FFmpeg 管道写入器相关
        self.use_ffmpeg_pipe = False
        self.ffmpeg_proc = None
        self.ffmpeg_stdin = None
        # 调试/诊断字段
        self._frames_written = 0
        self._writer_opened = False
        self._ffmpeg_stderr = None
        
        # 延迟初始化 mss，避免在导入时就初始化
        self.sct = None
        self.screen_width = None
        self.screen_height = None
        self.width = None
        self.height = None
        
        # 初始化屏幕捕获（延迟到需要时）
        try:
            self.sct = mss.mss()
            # 获取屏幕尺寸
            monitor = self.sct.monitors[1]  # 主显示器
            self.screen_width = monitor["width"]
            self.screen_height = monitor["height"]
            # 计算录制分辨率
            self.width = int(self.screen_width * self.scale_factor)
            self.height = int(self.screen_height * self.scale_factor)
            self.width = self.width - (self.width % 2)
            self.height = self.height - (self.height % 2)
            print(f"检测到屏幕分辨率: {self.screen_width}x{self.screen_height}")
            if self.scale_factor < 1.0:
                print(f"录制分辨率: {self.width}x{self.height} (缩放因子: {self.scale_factor})")
            print(f"目标帧率: {self.target_fps} FPS")
        except Exception as e:
            print(f"警告: 初始化屏幕捕获失败: {e}")
            # 使用默认值
            self.screen_width = 1920
            self.screen_height = 1080
            self.width = int(1920 * self.scale_factor)
            self.height = int(1080 * self.scale_factor)
            print(f"使用默认分辨率: {self.width}x{self.height}")
        
        # 事件队列（虽然不记录事件，但保持接口一致）
        self.events_queue = Queue()
        
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
                print(f"检测到屏幕分辨率: {self.width}x{self.height}")
                # 高分辨率提示
                if self.width >= 2560 or self.height >= 1440:
                    print(f"✓ 支持高分辨率录制: {self.width}x{self.height}")
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
        print(f"分辨率: {self.width}x{self.height}, FPS: {self.target_fps}")
        
        # 增加更兼容的编码器选项，优先使用通用的 mp4v（MP4）作为首选
        codecs_to_try = [
            ('MP4V', 'mp4v', '.mp4'),  # 通用 MP4 编码器（常见且兼容性好）
            ('H264', 'H264', '.mp4'),  # H.264 编码器，MP4 格式（若可用）
            ('X264', 'X264', '.mp4'),  # X.264 编码器，MP4 格式
            ('avc1', 'avc1', '.mp4'),  # AVC1 编码器，MP4 格式
            ('MJPG', 'MJPG', '.avi'),  # Motion JPEG，AVI 格式（备用）
            ('XVID', 'XVID', '.avi'),  # XVID 编码器，AVI 格式（备用）
            ('DIVX', 'DIVX', '.avi'),  # DivX 编码器，AVI 格式（备用）
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
                    self.target_fps,  # FPS
                    (int(self.width), int(self.height)),
                    True  # isColor=True (BGR 图像)
                )
                
                # 测试写入器是否可用
                if self.video_writer.isOpened():
                    print(f"  VideoWriter.isOpened() = True")
                    print(f"✓ 使用 {codec_name} 编码器初始化视频写入器成功")
                    self.video_path = video_path_actual
                    self._writer_opened = True
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
            # 若 OpenCV VideoWriter 无法初始化，尝试通过系统 ffmpeg 管道编码
            print("⚠️ 所有 OpenCV 视频编码器不可用，尝试使用系统 ffmpeg 管道写入...")
            ffmpeg_ok = False
            try:
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path:
                    # 启动 ffmpeg 进程，接收 rawvideo BGR24 stdin
                    width = int(self.width)
                    height = int(self.height)
                    output_str = str(self.video_path.absolute())
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
                    # 在Windows上隐藏控制台窗口
                    kwargs = {'stdin': subprocess.PIPE, 'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
                    if sys.platform == 'win32':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    proc = subprocess.Popen(cmd, **kwargs)
                    self.ffmpeg_proc = proc
                    self.ffmpeg_stdin = proc.stdin
                    self.use_ffmpeg_pipe = True
                    ffmpeg_ok = True
                else:
                    print("✗ 未在 PATH 中找到 ffmpeg 可执行文件")
            except Exception as e:
                print(f"✗ 启动 FFmpeg 时出错: {e}")
                import traceback
                traceback.print_exc()

            if not ffmpeg_ok:
                error_msg = "无法初始化视频写入器，所有编码器都不可用，且 FFmpeg 不可用。\n"
                error_msg += f"最后错误: {last_error}\n"
                error_msg += f"输出路径: {self.video_path.absolute()}\n"
                error_msg += f"OpenCV 版本: {cv2.__version__}\n"
                error_msg += "可能的原因:\n"
                error_msg += "1. OpenCV 未正确安装或缺少视频编码支持\n"
                error_msg += "2. 输出目录权限不足\n"
                error_msg += "3. 磁盘空间不足\n"
                error_msg += "4. 文件路径包含特殊字符\n"
                raise RuntimeError(error_msg)
        
        # 启动屏幕录制线程
        self.recording_thread = threading.Thread(target=self._record_screen)
        self.recording_thread.daemon = True
        self.recording_thread.start()

        # 初始化帧数计数
        try:
            self._frames_written = 0
        except Exception:
            pass
        
        return True
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return False
            
        self.is_recording = False
        
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
        
        elif self.use_ffmpeg_pipe:
            print("正在关闭 FFmpeg 管道并等待进程完成...")
            try:
                if self.ffmpeg_stdin:
                    try:
                        self.ffmpeg_stdin.close()
                    except Exception:
                        pass
                    self.ffmpeg_stdin = None
                if self.ffmpeg_proc:
                    try:
                        out, err = self.ffmpeg_proc.communicate(timeout=10)
                        if out:
                            print(f"FFmpeg stdout: {out.decode(errors='ignore')}")
                        if err:
                            decoded_err = err.decode(errors='ignore')
                            print(f"FFmpeg stderr: {decoded_err}")
                            self._ffmpeg_stderr = decoded_err
                    except subprocess.TimeoutExpired:
                        try:
                            self.ffmpeg_proc.kill()
                        except Exception:
                            pass
                    finally:
                        self.ffmpeg_proc = None
                if self.video_path.exists():
                    file_size = self.video_path.stat().st_size
                    print(f"✓ FFmpeg 输出文件已保存: {self.video_path}")
                    print(f"  文件大小: {file_size / (1024*1024):.2f} MB")
            except Exception as e:
                print(f"⚠️ 关闭 FFmpeg 管道时发生错误: {e}")
                import traceback
                traceback.print_exc()


        # 保存事件到JSON文件（空事件）
        self._save_events()
        
        return True
    
    def _record_screen(self):
        """录制屏幕（在单独线程中运行）"""
        # 在录制线程中创建 mss 实例，避免将主线程的 GDI 句柄传入子线程
        try:
            sct = mss.mss()
            monitor = sct.monitors[1]
        except Exception:
            # 回退到已有的 self.sct（如果有）
            if self.sct:
                sct = self.sct
                monitor = sct.monitors[1]
            else:
                print("✗ 无法初始化屏幕捕获（mss）")
                return
        frame_count = 0
        target_fps = self.target_fps
        frame_interval = 1.0 / target_fps  # 每帧间隔时间（秒）
        
        print(f"开始录制屏幕: 分辨率 {self.width}x{self.height}, FPS {target_fps}")
        
        # 使用基于时间戳的精确帧率控制
        # 记录录制开始时间（用于计算实际录制时长）
        recording_start_time = time.time()
        # 记录下一帧应该的时间戳
        next_frame_time = recording_start_time
        
        while self.is_recording:
            try:
                # 等待到下一帧的时间
                current_time = time.time()
                wait_time = next_frame_time - current_time
                if wait_time > 0:
                    time.sleep(wait_time)
                # 注意：即使延迟了，也不跳过帧，继续写入
                # 这样可以确保帧数与实际时间匹配
                # 如果延迟过大，会在下一帧时自动追赶
                
                # 捕获屏幕
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                
                # 转换颜色空间（BGRA to BGR）- 使用更快的方式
                img = img[:, :, :3]  # 直接切片去掉Alpha通道，比cvtColor更快
                
                # 确保图像尺寸正确（仅在必要时resize）
                if img.shape[1] != self.width or img.shape[0] != self.height:
                    img = cv2.resize(img, (self.width, self.height), interpolation=cv2.INTER_NEAREST)
                
                # 写入视频
                if self.use_ffmpeg_pipe:
                    # 将 BGR 原始帧写入 FFmpeg stdin
                    try:
                        if self.ffmpeg_stdin is None:
                            raise RuntimeError('FFmpeg stdin 未就绪')
                        if img.dtype != np.uint8:
                            img = img.astype(np.uint8)
                        if not img.flags['C_CONTIGUOUS']:
                            img = np.ascontiguousarray(img)
                        self.ffmpeg_stdin.write(img.tobytes())
                    except Exception as e:
                        print(f"⚠️ 写入 FFmpeg 帧异常 (帧 {frame_count}): {e}")
                    frame_count += 1
                elif self.video_writer and self.video_writer.isOpened():
                    try:
                        self.video_writer.write(img)
                    except Exception as e:
                        print(f"⚠️ 警告: 写入视频帧时发生异常 (帧 {frame_count}): {e}")
                    frame_count += 1
                    if frame_count % 300 == 0:  # 每10秒打印一次
                        elapsed_time = time.time() - recording_start_time
                        print(f"已录制 {frame_count} 帧 (实际时长: {elapsed_time:.1f} 秒, 理论时长: {frame_count/target_fps:.1f} 秒)")
                else:
                    print("⚠️ 警告: 视频写入器不可用")
                    break
                
                # 更新下一帧时间
                # 如果处理太慢（超过一帧间隔），从当前时间开始计算，避免累积延迟
                current_actual_time = time.time()
                if current_actual_time > next_frame_time + frame_interval:
                    # 处理太慢，从当前时间重新开始计时
                    next_frame_time = current_actual_time + frame_interval
                else:
                    # 正常情况，按固定间隔递增
                    next_frame_time += frame_interval
                if current_actual_time > next_frame_time + frame_interval:
                    # 如果延迟超过一帧，从当前时间重新开始，避免累积延迟
                    next_frame_time = current_actual_time + frame_interval
                else:
                    # 正常情况，按帧间隔递增
                    next_frame_time += frame_interval
            except Exception as e:
                print(f"⚠️ 录制屏幕时发生错误: {e}")
                import traceback
                traceback.print_exc()
                break
        
        # 计算实际录制时长
        recording_end_time = time.time()
        actual_duration = recording_end_time - recording_start_time
        expected_duration = frame_count / target_fps
        
        print(f"录制结束，共录制 {frame_count} 帧")
        print(f"实际录制时长: {actual_duration:.2f} 秒")
        print(f"理论视频时长: {expected_duration:.2f} 秒 (基于 {frame_count} 帧 @ {target_fps} fps)")
        if abs(actual_duration - expected_duration) > 0.5:
            print(f"⚠️ 警告: 实际时长与理论时长差异较大 ({abs(actual_duration - expected_duration):.2f} 秒)")
    
    def _save_events(self):
        """保存事件到JSON文件（空事件列表）"""
        events = []
        
        # 保存到JSON
        with open(self.events_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        return len(events)


