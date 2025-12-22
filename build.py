import PyInstaller.__main__
import os
import sys
import shutil

# 1. 确定分隔符 (Windows用分号;, Linux/Mac用冒号:)
sep = ';' if sys.platform.startswith('win') else ':'

# 2. 基础路径定义
base_path = os.path.abspath(".")
exe_name = 'SteamConverterPro'

# 3. 构造打包参数列表
params = [
    'main.py',
    f'--name={exe_name}',
    '--noconsole',
    '--onefile',
    '--clean',
    f'--add-data=backend{sep}backend',
    f'--add-data=frontend{sep}frontend',
    f'--add-data=bin{sep}bin',
    '--collect-all=webview',
    '--collect-all=flask',
    '--collect-all=flask_cors',
]

icon_path = os.path.join(base_path, "app_icon.ico")
if os.path.exists(icon_path):
    params.append(f'--icon={icon_path}')

# 4. 执行打包
try:
    print("🚀 正在开始打包，请稍候...")
    PyInstaller.__main__.run(params)
    print("✅ 打包完成！")
finally:
    # 5. 清理过程文件
    print("🧹 正在清理过程文件...")

    # 删除 build 文件夹
    build_dir = os.path.join(base_path, 'build')
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print(f" - 已删除临时目录: {build_dir}")

    # 删除 .spec 文件
    spec_file = os.path.join(base_path, f"{exe_name}.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f" - 已删除配置文件: {spec_file}")

    print(f"\n✨ 最终成品已生成在: {os.path.join(base_path, 'dist')}")