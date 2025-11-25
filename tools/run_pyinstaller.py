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
        '--onedir',
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

# If project contains a resources/fonts directory, include all TTFs as data so they are available at runtime
try:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    fonts_dir = os.path.join(base_dir, 'resources', 'fonts')
    if os.path.isdir(fonts_dir):
        for fn in os.listdir(fonts_dir):
            if fn.lower().endswith('.ttf') or fn.lower().endswith('.otf'):
                full = os.path.join(fonts_dir, fn)
                # Add data in Windows format: SOURCE;DEST_DIR
                args.append(f'--add-data={full};fonts')
                print(f'Including font in build: {full}')
except Exception:
    pass

# If no fonts are present in resources/fonts, try to fetch a recommended open-source font
try:
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent
    fonts_dir = base_dir / 'resources' / 'fonts'
    if not fonts_dir.exists() or not any(fonts_dir.glob('*.ttf')):
        print('No fonts found in resources/fonts; attempting to fetch Noto Sans...')
        try:
            # Attempt to run the helper fetch script in tools
            fetch_script = base_dir / 'tools' / 'fetch_noto.py'
            if fetch_script.exists():
                print('Running fetch_noto.py to download font...')
                import subprocess
                subprocess.check_call([sys.executable, str(fetch_script)])
        except Exception as e:
            print('Font fetch failed or unavailable:', e)
    # After possible fetch, include any fonts we have
    if fonts_dir.exists():
        for t in fonts_dir.glob('*.ttf'):
            args.append(f'--add-data={str(t)};fonts')
            print(f'Including font in build: {t}')
except Exception:
    pass

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
