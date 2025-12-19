# SteamClipExporter

一、 运行环境要求：
1. Python 3.x (推荐安装并配置好环境变量)
2. FFmpeg (必须下载并将其 bin 目录添加到系统环境变量 Path 中，否则转换将失败)

二、 部署步骤：

1. 安装 Python 依赖：
   打开命令行 (CMD 或 PowerShell)，进入 SteamConverter/backend 目录，执行以下命令：
   
   cd backend
   pip install Flask flask-cors

2. 运行服务器：
   双击根目录下的 run_server.bat 文件
   
3. 访问前端界面：
   服务器启动后，在浏览器中访问： http://127.0.0.1:5000/

三、 使用说明：
1. 在界面上方的输入框中，输入您的 Steam 录像根目录（例如：H:\Steam\clips）。
2. 点击“设置路径并扫描”。
3. 在左侧列表中多选您想转换的录像（选择顺序即为转换顺序）。
4. 点击“加入转换队列”。
5. 右侧将实时显示转换进度和柱状图。
