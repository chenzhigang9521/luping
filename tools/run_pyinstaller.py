"""
Run PyInstaller programmatically to avoid shell quoting issues.
This script reads environment variables `CV_FFMPEG_DLL` and `SYSTEM_FFMPEG` if set,
adds them to the `--add-binary` list, and runs PyInstaller with the same options
used in the batch script.
"""
import os
import sys
from PyInstaller.__main__ import run as pyi_run

cv_dll = os.environ.get('CV_FFMPEG_DLL')
sys_ffmpeg = os.environ.get('SYSTEM_FFMPEG')
import shutil
import os.path

# Validate environment values: ensure they point to actual files. If not, try to resolve ffmpeg via PATH.
if cv_dll:
    if not os.path.isfile(cv_dll):
        print(f"Warning: CV_FFMPEG_DLL set but file not found: {cv_dll}")
        cv_dll = None

if sys_ffmpeg:
    if not os.path.isfile(sys_ffmpeg):
        print(f"Warning: SYSTEM_FFMPEG set but file not found: {sys_ffmpeg}")
        # try to find ffmpeg in PATH
        which_ff = shutil.which('ffmpeg')
        if which_ff:
            print(f"Found ffmpeg in PATH: {which_ff}")
            sys_ffmpeg = which_ff
        else:
            sys_ffmpeg = None

args = [
    '--clean',
    '--noconfirm',
    '--onefile',
    '--windowed',
    '--name=ScreenRecorder',
    '--hidden-import=pynput',
    '--hidden-import=pynput.keyboard',
    '--hidden-import=pynput.mouse',
    '--hidden-import=pynput._util',
    '--hidden-import=pynput._util.win32',
    '--hidden-import=cv2',
    '--hidden-import=cv2.cv2',
    '--hidden-import=numpy',
    '--hidden-import=mss',
    '--collect-all', 'cv2',
]

# Add binaries using Windows-friendly SOURCE;DEST format
# Pass as a single token '--add-binary=SOURCE;DEST' to avoid parsing issues
if cv_dll:
    args.append(f'--add-binary={cv_dll};.')
if sys_ffmpeg:
    args.append(f'--add-binary={sys_ffmpeg};.')

# The script to build
args.append('luping\gui.py')

print('Running PyInstaller with args:')
print(' '.join(args))

# Run PyInstaller
try:
    pyi_run(args)
except SystemExit as e:
    # PyInstaller calls sys.exit; re-raise with code
    raise
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
