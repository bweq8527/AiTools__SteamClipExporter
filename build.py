import PyInstaller.__main__
import os
import sys
import shutil

# 配置区域
EXE_NAME = "SteamConverterPro"
SEP = ';' if sys.platform.startswith('win') else ':'
BASE_DIR = os.path.abspath(".")

params = [
    'main.py',
    f'--name={EXE_NAME}',
    '--noconsole',
    '--windowed',
    '--onefile',
    '--clean',
    f'--add-data=backend{SEP}backend',
    f'--add-data=frontend{SEP}frontend',
    f'--add-data=bin{SEP}bin',
    f'--add-data=app_icon.ico{SEP}.',
    '--collect-all=webview',
    '--collect-all=flask',
    '--collect-all=flask_cors',
]

if os.path.exists("app_icon.ico"):
    params.append(f'--icon=app_icon.ico')

try:
    print("🚀 正在构建商业级版本，请稍候...")
    PyInstaller.__main__.run(params)
    print(f"✅ 构建成功！成品位于 dist/{EXE_NAME}.exe")
finally:
    print("🧹 正在清理中间件...")
    for item in ['build', f"{EXE_NAME}.spec"]:
        if os.path.exists(item):
            if os.path.isdir(item): shutil.rmtree(item)
            else: os.remove(item)