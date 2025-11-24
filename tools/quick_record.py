from luping.recorder_no_pynput import ScreenRecorder
import time

if __name__ == '__main__':
    r = ScreenRecorder(output_dir="Resources/recordings")
    ok = r.start_recording()
    if not ok:
        print('无法开始录制')
    else:
        print('开始录制 4 秒...')
        time.sleep(4)
        r.stop_recording()
        print('录制完成')
        try:
            print('视频路径:', r.video_path)
            print('调试日志路径:', r._debug_log_path)
        except Exception:
            pass
