import os
import sys
import threading
import webview
from backend.app import app

def get_base_path():
    """获取程序运行时的根目录，适配开发环境和 PyInstaller 环境"""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")

def start_flask():
    # 商业版建议关闭 debug 模式
    app.run(port=5000, debug=False, threaded=True)

if __name__ == '__main__':
    # 启动后台 Flask 线程
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    # 创建原生桌面窗口
    # url 直接指向 Flask 地址
    window = webview.create_window(
        title='Steam Recorder Converter Pro',
        url='http://127.0.0.1:5000',
        width=1200,
        height=800,
        background_color='#121212'
    )

    # 启动窗口，不使用浏览器，直接在 native 窗口运行
    webview.start()