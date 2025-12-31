import os
import sys
import logging
import threading
import queue
import glob
import webview
import re
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS


def get_res_path(rel_path):
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)


app = Flask(__name__, static_folder=get_res_path('frontend'), static_url_path='')
CORS(app)

try:
    from backend.worker import convert_clip, generate_quick_thumb
except ImportError:
    from worker import convert_clip, generate_quick_thumb

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

CONVERSION_QUEUE = queue.Queue()
CONVERSION_STATUS = {}
CURRENT_CLIP_PATH = None
EXPORT_PATH = None
PYTHON_LOGS = []


def add_py_log(msg):
    PYTHON_LOGS.append(msg)
    if len(PYTHON_LOGS) > 100: PYTHON_LOGS.pop(0)


def worker_thread():
    while True:
        item = CONVERSION_QUEUE.get()
        if item is None: break
        folder, out, cid = item
        CONVERSION_STATUS[cid]['status'] = 'running'
        add_py_log(f"开始转换: {cid}")
        try:
            convert_clip(folder, out, CONVERSION_STATUS[cid])
            add_py_log(f"转换完成: {cid}")
        except Exception as e:
            CONVERSION_STATUS[cid]['status'] = 'error'
            CONVERSION_STATUS[cid]['eta'] = str(e)
            add_py_log(f"转换出错: {str(e)}")
        CONVERSION_QUEUE.task_done()


threading.Thread(target=worker_thread, daemon=True).start()


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/select_folder', methods=['GET'])
def select_folder():
    window = app.config.get('WEBVIEW_WINDOW')
    if window:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return jsonify({"success": True, "path": result[0]})
    return jsonify({"success": False, "path": ""})


@app.route('/api/open_folder', methods=['POST'])
def open_folder():
    path = request.json.get('path', '')
    if os.path.exists(path):
        os.startfile(path)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400


@app.route('/api/thumbnail/<cid>')
def get_thumb(cid):
    if CURRENT_CLIP_PATH:
        return send_from_directory(CURRENT_CLIP_PATH, f"{cid}.jpg")
    return "404", 404


@app.route('/api/set_path', methods=['POST'])
def set_p():
    global CURRENT_CLIP_PATH, EXPORT_PATH
    p = request.json.get('path', '').strip()
    e = request.json.get('export_path', '').strip()
    if os.path.isdir(p):
        c_p = os.path.join(p, 'clips')
        CURRENT_CLIP_PATH = c_p if os.path.isdir(c_p) else p
        EXPORT_PATH = e if (e and os.path.isdir(e)) else CURRENT_CLIP_PATH
        add_py_log(f"配置就绪 | 素材: {CURRENT_CLIP_PATH} | 导出: {EXPORT_PATH}")
        return jsonify({"success": True, "message": "目录配置成功"})
    return jsonify({"success": False, "message": "无效的素材路径"}), 400


@app.route('/api/clips', methods=['GET'])
def list_c():
    if not CURRENT_CLIP_PATH or not os.path.exists(CURRENT_CLIP_PATH):
        return jsonify({"clips": []})
    clips = []
    try:
        all_entries = glob.glob(os.path.join(CURRENT_CLIP_PATH, 'clip_*'))
        for entry in all_entries:
            if not os.path.isdir(entry): continue
            cid = os.path.basename(entry)

            # --- 优化：从文件名解析 SteamID 和时间 ---
            # 格式: clip_2357570_20241112_145705
            name_parts = cid.split('_')
            steam_id = "Unknown"
            m_time = os.path.getmtime(entry)  # 兜底时间

            if len(name_parts) >= 4:
                steam_id = name_parts[1]
                date_str = name_parts[2]
                time_str = name_parts[3]
                try:
                    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                    m_time = dt.timestamp()
                except:
                    pass

            game_name = f"AppID {steam_id}"  # 默认显示 ID
            g_path = os.path.join(entry, 'gamename.txt')
            if os.path.exists(g_path):
                try:
                    with open(g_path, 'r', encoding='utf-8') as f:
                        name_from_file = f.read().strip()
                        if name_from_file: game_name = name_from_file
                except:
                    pass

            t_path = os.path.join(CURRENT_CLIP_PATH, f"{cid}.jpg")
            if not os.path.exists(t_path):
                try:
                    generate_quick_thumb(entry, t_path)
                except:
                    pass

            check_target = os.path.join(EXPORT_PATH, f"{cid}.mp4")
            is_done = os.path.exists(check_target)

            clips.append({
                "id": cid,
                "game": game_name,
                "time": m_time,
                "is_converted": is_done,
                "thumb": f"/api/thumbnail/{cid}" if os.path.exists(t_path) else None,
                "status": CONVERSION_STATUS.get(cid, {}).get('status', 'idle')
            })
    except Exception as e:
        add_py_log(f"扫描错误: {str(e)}")
    return jsonify({"clips": clips})


@app.route('/api/queue', methods=['POST'])
def add_q():
    ids = request.json.get('clip_ids', [])
    for cid in ids:
        status_info = CONVERSION_STATUS.get(cid, {})
        if status_info.get('status') not in ['pending', 'running']:
            CONVERSION_STATUS[cid] = {'status': 'pending', 'progress': 0, 'eta': '排队中'}
            target_dir = EXPORT_PATH if EXPORT_PATH else CURRENT_CLIP_PATH
            CONVERSION_QUEUE.put((os.path.join(CURRENT_CLIP_PATH, cid), os.path.join(target_dir, f"{cid}.mp4"), cid))
            add_py_log(f"加入队列: {cid}")
    return jsonify({"success": True})


@app.route('/api/progress')
def get_prog():
    return jsonify({"all_statuses": CONVERSION_STATUS, "py_logs": PYTHON_LOGS})