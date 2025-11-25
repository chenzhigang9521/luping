import sys
import traceback
import time
from pathlib import Path

# Ensure project path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk
from luping.gui import RecorderGUI
import tkinter.font as tkfont


def run_test(chosen=None):
    try:
        root = tk.Tk()
        root.withdraw()  # keep window hidden
        app = RecorderGUI(root)

        fams = getattr(app, '_available_families', [])
        if not chosen:
            chosen = fams[0] if fams else 'Arial'

        print('Chosen to apply:', chosen)

        # record defaults before
        try:
            before = tkfont.nametofont('TkDefaultFont').actual()
        except Exception as e:
            before = {'error': str(e)}
        print('before TkDefaultFont:', before)

        # set var and call apply
        try:
            app._font_var.set(chosen)
        except Exception as e:
            print('set var failed:', e)
        try:
            app._apply_font_from_selector()
        except Exception as e:
            print('apply method raised:', e)
            traceback.print_exc()

        # small sleep to let after-effects run
        root.update_idletasks()
        time.sleep(0.2)

        try:
            after = tkfont.nametofont('TkDefaultFont').actual()
        except Exception as e:
            after = {'error': str(e)}
        print('after TkDefaultFont:', after)

        # shared fonts
        shared = {}
        for name in ('font_ui','font_title','font_button','font_status','font_small'):
            obj = getattr(app, name, None)
            if obj is None:
                shared[name] = None
            else:
                try:
                    shared[name] = obj.actual()
                except Exception as e:
                    shared[name] = {'error': str(e)}
        print('shared fonts after apply:', shared)

        # cleanup
        try:
            root.destroy()
        except Exception:
            pass
    except Exception as e:
        print('Fatal error in test:', e)
        traceback.print_exc()


if __name__ == '__main__':
    run_test()
