"""
检查视频文件是否有效的工具脚本
用法: python 检查视频文件.py <视频文件路径>
"""
import sys
import cv2
from pathlib import Path

def check_video_file(video_path):
    """检查视频文件"""
    video_path = Path(video_path)
    
    print("=" * 60)
    print(f"检查视频文件: {video_path}")
    print("=" * 60)
    
    # 1. 检查文件是否存在
    if not video_path.exists():
        print("❌ 错误: 文件不存在")
        return False
    
    print(f"✓ 文件存在")
    
    # 2. 检查文件大小
    file_size = video_path.stat().st_size
    print(f"✓ 文件大小: {file_size:,} 字节 ({file_size / (1024*1024):.2f} MB)")
    
    if file_size == 0:
        print("❌ 错误: 文件大小为 0")
        return False
    
    # 3. 检查文件头
    print("\n检查文件头...")
    try:
        with open(video_path, 'rb') as f:
            header = f.read(16)
            print(f"前16字节 (hex): {header.hex()}")
            print(f"前16字节 (ascii): {header}")
            
            if video_path.suffix == '.mp4':
                if header[4:8] == b'ftyp':
                    print("✓ MP4 文件头正确 (ftyp box)")
                else:
                    print("⚠️ 警告: MP4 文件头可能不正确")
                    print(f"   4-8字节应该是 'ftyp'，实际是: {header[4:8]}")
            elif video_path.suffix == '.avi':
                if header[:4] == b'RIFF':
                    print("✓ AVI 文件头正确 (RIFF)")
                else:
                    print("⚠️ 警告: AVI 文件头可能不正确")
                    print(f"   前4字节应该是 'RIFF'，实际是: {header[:4]}")
    except Exception as e:
        print(f"⚠️ 读取文件头时出错: {e}")
    
    # 4. 用 OpenCV 检查
    print("\n用 OpenCV 检查视频...")
    cap = cv2.VideoCapture(str(video_path))
    
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
    duration = frame_count / fps if fps > 0 else 0
    
    print(f"✓ OpenCV 可以打开视频")
    print(f"  帧率 (FPS): {fps}")
    print(f"  总帧数: {frame_count}")
    print(f"  分辨率: {width}x{height}")
    print(f"  时长: {duration:.2f} 秒")
    print(f"  编码器 (FourCC): {fourcc_str} ({fourcc})")
    
    if frame_count == 0:
        print("❌ 错误: 视频没有帧数据")
        cap.release()
        return False
    
    # 尝试读取帧
    print("\n尝试读取帧...")
    frames_read = 0
    for i in range(min(10, frame_count)):  # 读取前10帧
        ret, frame = cap.read()
        if ret:
            frames_read += 1
            if i == 0:
                print(f"✓ 可以读取第1帧，尺寸: {frame.shape}")
        else:
            print(f"⚠️ 警告: 无法读取第 {i+1} 帧")
            break
    
    print(f"✓ 成功读取 {frames_read} 帧")
    
    # 尝试读取最后一帧
    if frame_count > 1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)
        ret, frame = cap.read()
        if ret:
            print(f"✓ 可以读取最后一帧 (第 {frame_count} 帧)")
        else:
            print("⚠️ 警告: 无法读取最后一帧")
    
    cap.release()
    
    print("\n" + "=" * 60)
    if frames_read > 0:
        print("✓ 视频文件验证通过")
        return True
    else:
        print("❌ 视频文件验证失败")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python 检查视频文件.py <视频文件路径>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    success = check_video_file(video_path)
    sys.exit(0 if success else 1)

