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


class ScreenRecorder:
    """屏幕录制器（仅录制屏幕，不记录键盘和鼠标）"""
    
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
        codecs_to_try = [
            ('H264', 'H264', '.mp4'),  # H.264 编码器，MP4 格式（最佳选择）
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
                    30.0,  # FPS
                    (int(self.width), int(self.height)),
                    True  # isColor=True (BGR 图像)
                )
                
                # 测试写入器是否可用
                if self.video_writer.isOpened():
                    print(f"  VideoWriter.isOpened() = True")
                    # 尝试写入一个测试帧来验证
                    test_frame = np.zeros((int(self.height), int(self.width), 3), dtype=np.uint8)
                    write_result = self.video_writer.write(test_frame)
                    if write_result:
                        print(f"✓ 使用 {codec_name} 编码器初始化视频写入器成功")
                        # 更新视频路径（可能因为编码器改变了扩展名）
                        self.video_path = video_path_actual
                        # 释放测试帧占用的资源
                        self.video_writer.release()
                        # 重新创建写入器（不使用测试帧）
                        self.video_writer = cv2.VideoWriter(
                            video_path_str,
                            fourcc,
                            30.0,
                            (int(self.width), int(self.height)),
                            True
                        )
                        if self.video_writer.isOpened():
                            break
                        else:
                            print(f"⚠️ {codec_name} 编码器重新初始化失败")
                            self.video_writer = None
                    else:
                        print(f"⚠️ {codec_name} 编码器无法写入测试帧")
                        self.video_writer.release()
                        self.video_writer = None
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
            error_msg = "无法初始化视频写入器，所有编码器都不可用。\n"
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
        
        # 保存事件到JSON文件（空事件）
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
    
    def _save_events(self):
        """保存事件到JSON文件（空事件列表）"""
        events = []
        
        # 保存到JSON
        with open(self.events_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        return len(events)


