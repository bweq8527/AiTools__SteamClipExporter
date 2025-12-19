@echo off
set FLASK_APP=backend.app

echo ----------------------------------------
echo Steam Converter 启动脚本
echo ----------------------------------------

:: 检查 Python 环境
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python。请确保 Python 已安装并添加到系统 PATH 环境变量中。
    goto :end
)

:: 检查 FFmpeg 环境
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo 警告: 未找到 FFmpeg。程序仍会启动，但转换功能会失败。
    echo 请将 FFmpeg 的 bin 目录添加到系统 PATH 环境变量中。
)

echo 正在安装/检查依赖...
python -m pip install Flask flask-cors >nul 2>&1

echo 正在启动 Flask 服务器...
echo 访问地址: http://127.0.0.1:5000/
echo.

:: 启动服务器
python -m flask run

:end
echo.
pause