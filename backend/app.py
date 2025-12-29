import os
import sys
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import queue
import glob

# 禁用 Werkzeug 日志，防止打包后弹出 CMD
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

try:
    from worker import convert_clip, generate_quick_thumb
except:
    from .worker import convert_clip, generate_quick_thumb

def get_res_path(rel_path):
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

app = Flask(__name__, static_folder=get_res_path('frontend'))
CORS(app)

CONVERSION_QUEUE = queue.Queue()
CONVERSION_STATUS = {}
CURRENT_CLIP_PATH = None

def worker_thread():
    while True:
        folder, out, cid = CONVERSION_QUEUE.get()
        CONVERSION_STATUS[cid]['status'] = 'running'
        convert_clip(folder, out, CONVERSION_STATUS[cid])
        CONVERSION_QUEUE.task_done()

threading.Thread(target=worker_thread, daemon=True).start()

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/thumbnail/<cid>')
def get_thumb(cid):
    if CURRENT_CLIP_PATH: return send_from_directory(CURRENT_CLIP_PATH, f"{cid}.jpg")
    return "404", 404

@app.route('/api/set_path', methods=['POST'])
def set_p():
    global CURRENT_CLIP_PATH
    p = request.json.get('path', '').strip()
    if os.path.isdir(p):
        c_p = os.path.join(p, 'clips')
        CURRENT_CLIP_PATH = c_p if os.path.isdir(c_p) else p
        return jsonify({"success": True})
    return jsonify({"success": False}), 400


@app.route('/api/clips', methods=['GET'])
def list_c():
    if not CURRENT_CLIP_PATH or not os.path.exists(CURRENT_CLIP_PATH):
        return jsonify({"clips": []})

    clips = []
    try:
        # 获取所有以 clip_ 开头的路径
        all_entries = glob.glob(os.path.join(CURRENT_CLIP_PATH, 'clip_*'))

        for entry in all_entries:
            # 【关键修复】：只处理文件夹，跳过生成的 .mp4 和 .jpg 文件
            if not os.path.isdir(entry):
                continue

            cid = os.path.basename(entry)

            # 检查内部视频数据目录是否存在（防止处理正在拷贝中的残缺文件夹）
            video_data_dir = os.path.join(entry, 'video')
            if not os.path.exists(video_data_dir):
                continue

            t_path = os.path.join(CURRENT_CLIP_PATH, f"{cid}.jpg")

            # 生成缩略图保护逻辑
            if not os.path.exists(t_path):
                try:
                    # 只有当文件夹内确实有数据时才生成
                    generate_quick_thumb(entry, t_path)
                except:
                    pass

            # 检查是否已经转换过
            is_done = os.path.exists(os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"))

            clips.append({
                "id": cid,
                "is_converted": is_done,
                "thumb": f"/api/thumbnail/{cid}" if os.path.exists(t_path) else None,
                "status": CONVERSION_STATUS.get(cid, {}).get('status', 'idle')
            })
    except Exception as e:
        # 记录错误防止前端收到 undefined
        app.logger.error(f"Scan Error: {e}")

    return jsonify({"clips": clips})
@app.route('/api/queue', methods=['POST'])
def add_q():
    ids = request.json.get('clip_ids', [])
    for cid in ids:
        if CONVERSION_STATUS.get(cid, {}).get('status') not in ['pending', 'running']:
            CONVERSION_STATUS[cid] = {'status': 'pending', 'progress': 0, 'eta': '排队中'}
            CONVERSION_QUEUE.put((os.path.join(CURRENT_CLIP_PATH, cid), os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"), cid))
    return jsonify({"success": True})

@app.route('/api/progress')
def get_prog():
    return jsonify({"all_statuses": CONVERSION_STATUS})