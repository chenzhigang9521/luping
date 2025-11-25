"""
Font / Tk probe utility
Run this with the same Python environment (or pack it into the exe) to print detailed info
about available font families, named fonts, Tk/Tcl versions, and check for Segoe UI font files.
"""
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
import sys
import ctypes

def check_windows_font_files(font_names):
    paths = []
    if sys.platform.startswith('win'):
        font_dir = Path(r"C:\Windows\Fonts")
        for name in font_names:
            # common segoe ui filenames
            candidates = [
                'segoeui.ttf','segoeuib.ttf','segoeuiz.ttf','segoeuii.ttf',
                'segoeui.ttf'
            ]
            found = []
            for c in candidates:
                fp = font_dir / c
                if fp.exists():
                    found.append(str(fp))
            paths.append((name, found))
    return paths


def main():
    root = tk.Tk()
    root.withdraw()

    families = sorted(list(tkfont.families()))
    print('Available font families count:', len(families))
    for f in families[:120]:
        print('  ', f)

    preferred = ['Segoe UI','Microsoft YaHei','Arial','Tahoma']
    for p in preferred:
        print('Preferred:', p, '->', p in families)

    print('\nNamed fonts:')
    names = ['TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont']
    for n in names:
        try:
            print(' ', n, tkfont.nametofont(n).actual())
        except Exception as e:
            print(' ', n, 'missing or error:', e)

    print('\nTk/Tcl versions:', tk.TkVersion, tk.TclVersion)

    try:
        scaling = root.tk.call('tk','scaling')
    except Exception:
        scaling = None
    print('tk scaling:', scaling)
    print('screen pixels:', root.winfo_screenwidth(), 'x', root.winfo_screenheight())
    print('screen mm:', root.winfo_screenmmwidth(), 'x', root.winfo_screenmmheight())

    if sys.platform.startswith('win'):
        print('\nCheck Segoe UI font files in C:\\Windows\\Fonts:')
        for name, found in check_windows_font_files(['Segoe UI']):
            print(name, 'found files:', found)

    # Also attempt to query font used by a small test label
    try:
        lbl = tk.Label(root, text='测试字体AaBb', font=('Segoe UI', 12))
        lbl.pack()
        root.update_idletasks()
        actual = tkfont.Font(font=lbl.cget('font')).actual()
        print('\nTest label font actual:', actual)
    except Exception as e:
        print('Test label font creation failed:', e)

    root.destroy()

if __name__ == '__main__':
    main()
