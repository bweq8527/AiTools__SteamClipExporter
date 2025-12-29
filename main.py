import os
import sys
import threading
import webview
from backend.app import app

def get_base_path():
    if hasattr(sys, '_MEIPASS'): return sys._MEIPASS
    return os.path.abspath(".")

def start_flask():
    app.run(port=5000, debug=False, threaded=True, host='127.0.0.1')

if __name__ == '__main__':
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    icon_p = os.path.join(get_base_path(), "app_icon.ico")
    window = webview.create_window(
        title='Steam Video Converter Pro',
        url='http://127.0.0.1:5000',
        width=1650,
        height=1000,
        background_color='#121212'
    )

    app.config['WEBVIEW_WINDOW'] = window

    if os.path.exists(icon_p):
        webview.start(debug=False, icon=icon_p)
    else:
        webview.start(debug=False)