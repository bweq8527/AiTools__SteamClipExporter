import os
import sys
import glob
import re
import time
import queue
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from .worker import convert_clip  # 注意这里的相对导入

# --- 全局状态管理 ---
# 获取当前 app.py 所在的绝对路径
base_dir = os.path.dirname(os.path.abspath(__file__))
# 获取 SteamConverter 根目录 (即 backend 的上一级)
root_dir = os.path.dirname(base_dir)
# 定义前端文件夹的绝对路径
frontend_dir = os.path.join(root_dir, 'frontend')

# 重新初始化 app，显式指定绝对路径
app = Flask(__name__,
            static_url_path='',
            static_folder=frontend_dir)

@app.route('/')
def index():
    # 使用绝对路径发送文件
    return send_from_directory(frontend_dir, 'index.html')
app = Flask(__name__, static_url_path='', static_folder='../frontend')
CORS(app)  # 允许跨域请求
CONVERSION_QUEUE = queue.Queue()  # 任务队列
CONVERSION_STATUS = {}  # 实时进度字典: {clip_id: {status: 'idle'|'running'|'done', progress: 0-100, eta: 'X min'}}
CURRENT_CLIP_PATH = None  # Steam 录像根目录
WORKER_THREAD = None


def worker_thread_func():
    """后台工作线程，负责从队列取出任务并执行转换。"""
    global CONVERSION_STATUS
    while True:
        try:
            # 获取下一个任务 (clip_folder, output_path, clip_id)
            clip_folder, output_path, clip_id = CONVERSION_QUEUE.get(timeout=1)
        except queue.Empty:
            time.sleep(1)
            continue

        print(f"开始处理: {clip_id}")
        CONVERSION_STATUS[clip_id]['status'] = 'running'

        # 调用 worker.py 中的核心转换函数
        convert_clip(clip_folder, output_path, CONVERSION_STATUS[clip_id])

        # 任务完成（如果 worker.py 没有设置 error，则此处认为是完成）
        if CONVERSION_STATUS[clip_id]['status'] != 'error':
            CONVERSION_STATUS[clip_id]['status'] = 'done'
            CONVERSION_STATUS[clip_id]['progress'] = 100
            print(f"任务完成: {clip_id}")
        else:
            print(f"任务失败: {clip_id}")

        CONVERSION_QUEUE.task_done()


# 启动工作线程
WORKER_THREAD = threading.Thread(target=worker_thread_func, daemon=True)
WORKER_THREAD.start()


# --- API 接口定义 ---

@app.route('/api/set_path', methods=['POST'])
def set_path():
    """设置 Steam 录像根目录"""
    global CURRENT_CLIP_PATH
    data = request.json
    path = data.get('path')

    # 清理路径，确保是目录
    if path:
        path = os.path.normpath(path)

    if path and os.path.isdir(path):
        # 验证 clips 文件夹是否存在
        clips_path = os.path.join(path, 'clips')
        if not os.path.isdir(clips_path):
            # 尝试直接使用 path 作为 clips 目录
            CURRENT_CLIP_PATH = path
            return jsonify({"success": True, "message": f"路径设置成功: {path} (假设此为clips目录)"})

        CURRENT_CLIP_PATH = clips_path
        return jsonify({"success": True, "message": f"路径设置成功: {clips_path}"})

    return jsonify({"success": False, "message": "路径无效或不存在"}), 400


@app.route('/api/clips', methods=['GET'])
def list_clips():
    """扫描目录并返回所有可转换的录像列表"""
    if not CURRENT_CLIP_PATH:
        return jsonify({"success": False, "message": "请先设置录像根目录"}), 400

    clips = []
    # 查找所有 clip_... 的文件夹
    clip_dirs = glob.glob(os.path.join(CURRENT_CLIP_PATH, 'clip_*'))

    for clip_dir in clip_dirs:
        clip_id = os.path.basename(clip_dir)

        # 检查 clip 文件夹下是否有 video/fg_* 结构，确保它是可转换的录像
        if not glob.glob(os.path.join(clip_dir, 'video', 'fg_*')):
            continue

        # 估算文件大小/时长作为参考
        size_bytes = 0
        try:
            size_bytes = sum(os.path.getsize(os.path.join(dirpath, filename))
                             for dirpath, dirnames, filenames in os.walk(clip_dir)
                             for filename in filenames)
        except OSError:
            # 某些文件可能被Steam锁定
            pass

        # 检查是否已转换
        is_converted = os.path.exists(os.path.join(CURRENT_CLIP_PATH, f"{clip_id}.mp4"))

        clips.append({
            "id": clip_id,
            "path": clip_dir,
            "name": clip_id,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "is_converted": is_converted,
            "status": CONVERSION_STATUS.get(clip_id, {}).get('status', 'idle')
        })

    return jsonify({"success": True, "clips": clips})


@app.route('/api/queue', methods=['POST'])
def add_to_queue():
    """添加选中的录像到转换队列"""
    global CONVERSION_STATUS
    clip_ids = request.json.get('clip_ids', [])
    if not CURRENT_CLIP_PATH:
        return jsonify({"success": False, "message": "请先设置录像根目录"}), 400

    new_jobs = 0
    for clip_id in clip_ids:
        # 检查是否已经在队列或已完成
        current_status = CONVERSION_STATUS.get(clip_id, {}).get('status', 'idle')
        if current_status in ('running', 'done'):
            continue

        clip_folder = os.path.join(CURRENT_CLIP_PATH, clip_id)
        output_path = os.path.join(CURRENT_CLIP_PATH, f"{clip_id}.mp4")

        # 检查文件夹是否存在
        if not os.path.isdir(clip_folder):
            continue

        # 初始化状态
        CONVERSION_STATUS[clip_id] = {'status': 'pending', 'progress': 0, 'eta': '待计算'}

        # 放入队列
        CONVERSION_QUEUE.put((clip_folder, output_path, clip_id))
        new_jobs += 1

    return jsonify({"success": True, "message": f"成功添加 {new_jobs} 个任务到队列"})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """获取所有任务的实时进度和队列状态"""

    # 构造队列列表 (用于前端实时更新图表和队列)
    queue_data = {}

    # 遍历 CONVERSION_STATUS 字典，包含所有状态信息
    for clip_id, status_info in CONVERSION_STATUS.items():
        queue_data[clip_id] = status_info

    # 找出当前正在运行的任务 (如果需要，但 all_statuses 已经包含了)

    return jsonify({
        "success": True,
        "total_queue_size": CONVERSION_QUEUE.qsize(),
        "all_statuses": queue_data  # 传递所有状态信息
    })


# 提供静态文件
@app.route('/')
def index():
    # 默认返回 frontend/index.html
    return send_from_directory('../frontend', 'index.html')


if __name__ == '__main__':
    # 注意：在生产环境中应使用 Gunicorn/Waitress 等 WSGI 服务器
    print("Flask Server running on http://127.0.0.1:5000")
    # debug=True 用于开发，threaded=False 确保我们自己管理的工作线程稳定
    app.run(debug=True, threaded=False)