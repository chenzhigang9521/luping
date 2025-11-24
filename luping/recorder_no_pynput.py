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
        
        # 创建输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_path = self.output_dir / f"recording_{timestamp}.avi"
        self.events_path = self.output_dir / f"events_{timestamp}.json"
        
        # 初始化视频写入器
        # 尝试多个编码器，按优先级顺序
        codecs_to_try = [
            ('XVID', 'XVID'),  # XVID 编码器，兼容性好
            ('MJPG', 'MJPG'),  # Motion JPEG，兼容性最好
            ('X264', 'X264'),  # H.264 编码器（如果可用）
            ('mp4v', 'mp4v'),  # 原始编码器（作为最后备选）
        ]
        
        self.video_writer = None
        for codec_name, fourcc_code in codecs_to_try:
            try:
                fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                self.video_writer = cv2.VideoWriter(
                    str(self.video_path),
                    fourcc,
                    30.0,  # FPS
                    (self.width, self.height)
                )
                # 测试写入器是否可用
                if self.video_writer.isOpened():
                    print(f"✓ 使用 {codec_name} 编码器初始化视频写入器成功")
                    break
                else:
                    print(f"⚠️ {codec_name} 编码器初始化失败，尝试下一个...")
                    self.video_writer.release()
                    self.video_writer = None
            except Exception as e:
                print(f"⚠️ {codec_name} 编码器不可用: {e}")
                if self.video_writer:
                    self.video_writer.release()
                    self.video_writer = None
                continue
        
        if self.video_writer is None or not self.video_writer.isOpened():
            raise RuntimeError("无法初始化视频写入器，所有编码器都不可用")
        
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
            self.video_writer.release()
        
        # 保存事件到JSON文件（空事件）
        self._save_events()
        
        return True
    
    def _record_screen(self):
        """录制屏幕（在单独线程中运行）"""
        monitor = self.sct.monitors[1]
        
        while self.is_recording:
            # 捕获屏幕
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            
            # 转换颜色空间（BGRA to BGR）
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # 写入视频
            if self.video_writer:
                self.video_writer.write(img)
            
            # 控制帧率（约30fps）
            time.sleep(1/30)
    
    def _save_events(self):
        """保存事件到JSON文件（空事件列表）"""
        events = []
        
        # 保存到JSON
        with open(self.events_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        
        return len(events)


