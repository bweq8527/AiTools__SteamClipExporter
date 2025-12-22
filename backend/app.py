import os
import sys
import glob
import queue
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 兼容性导入
try:
    from worker import convert_clip, generate_quick_thumb
except ImportError:
    from .worker import convert_clip, generate_quick_thumb

# 路径适配逻辑
def get_res_path(rel_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

frontend_dir = get_res_path('frontend')
app = Flask(__name__, static_folder=frontend_dir)
CORS(app)

CONVERSION_QUEUE = queue.Queue()
CONVERSION_STATUS = {}
CURRENT_CLIP_PATH = None

def worker_thread():
    while True:
        try:
            folder, out, cid = CONVERSION_QUEUE.get()
            CONVERSION_STATUS[cid]['status'] = 'running'
            convert_clip(folder, out, CONVERSION_STATUS[cid])
            CONVERSION_QUEUE.task_done()
        except: continue

threading.Thread(target=worker_thread, daemon=True).start()

@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/api/thumbnail/<cid>')
def get_thumb(cid):
    if CURRENT_CLIP_PATH:
        return send_from_directory(CURRENT_CLIP_PATH, f"{cid}.jpg")
    return "404", 404

@app.route('/api/set_path', methods=['POST'])
def set_p():
    global CURRENT_CLIP_PATH
    p = request.json.get('path', '').strip()
    if os.path.isdir(p):
        c_p = os.path.join(p, 'clips')
        CURRENT_CLIP_PATH = c_p if os.path.isdir(c_p) else p
        return jsonify({"success": True, "message": f"目录已锁定: {CURRENT_CLIP_PATH}"})
    return jsonify({"success": False, "message": "无效路径"}), 400

@app.route('/api/clips', methods=['GET'])
def list_c():
    if not CURRENT_CLIP_PATH: return jsonify({"clips": []})
    clips = []
    for d in glob.glob(os.path.join(CURRENT_CLIP_PATH, 'clip_*')):
        if os.path.isdir(d):
            cid = os.path.basename(d)
            t_path = os.path.join(CURRENT_CLIP_PATH, f"{cid}.jpg")
            if not os.path.exists(t_path): generate_quick_thumb(d, t_path)
            is_done = os.path.exists(os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"))
            clips.append({
                "id": cid, "is_converted": is_done,
                "thumb": f"/api/thumbnail/{cid}" if os.path.exists(t_path) else None,
                "status": CONVERSION_STATUS.get(cid, {}).get('status', 'idle')
            })
    return jsonify({"clips": clips})

@app.route('/api/queue', methods=['POST'])
def add_q():
    ids = request.json.get('clip_ids', [])
    for cid in ids:
        if CONVERSION_STATUS.get(cid, {}).get('status') not in ['pending', 'running']:
            CONVERSION_STATUS[cid] = {'status': 'pending', 'progress': 0, 'eta': '等待中'}
            CONVERSION_QUEUE.put((os.path.join(CURRENT_CLIP_PATH, cid), os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"), cid))
    return jsonify({"success": True})

@app.route('/api/progress')
def get_prog():
    return jsonify({"all_statuses": CONVERSION_STATUS})