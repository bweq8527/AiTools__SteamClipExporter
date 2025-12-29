import os
import sys
import threading
import webview
from backend.app import app


def get_base_path():
    if hasattr(sys, '_MEIPASS'): return sys._MEIPASS
    return os.path.abspath(".")


def start_flask():
    # 彻底关闭 debug，防止干扰
    app.run(port=5000, debug=False, threaded=True, host='127.0.0.1')


if __name__ == '__main__':
    # 1. 启动 Flask 线程
    threading.Thread(target=start_flask, daemon=True).start()

    # 2. 获取图标路径
    icon_p = os.path.join(get_base_path(), "app_icon.ico")

    # 3. 创建原生窗口 (移除报错的 icon 参数)
    window = webview.create_window(
        title='Steam Video Converter Pro',
        url='http://127.0.0.1:5000',
        width=1100,
        height=750,
        background_color='#121212'
    )

    # 4. 在 start 函数中通过 icon 参数设置图标
    # 这样设置会同时应用到窗口左上角和任务栏
    if os.path.exists(icon_p):
        webview.start(debug=False, icon=icon_p)
    else:
        webview.start(debug=False)