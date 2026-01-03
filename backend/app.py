import os
import sys
import logging
import threading
import queue
import glob
import webview
import re
import subprocess
import tempfile
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS


def get_res_path(rel_path):
    if hasattr(sys, '_MEIPASS'): return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)


app = Flask(__name__, static_folder=get_res_path('frontend'), static_url_path='')
CORS(app)

try:
    from backend.worker import convert_clip, generate_quick_thumb, get_ffmpeg_tool, get_hide_config
except ImportError:
    from worker import convert_clip, generate_quick_thumb, get_ffmpeg_tool, get_hide_config

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


# --- 修正后的流媒体预览接口 ---
@app.route('/api/stream/<cid>')
def stream_clip(cid):
    if not CURRENT_CLIP_PATH: return "Path not set", 400
    folder = os.path.join(CURRENT_CLIP_PATH, cid)
    # 查找视频文件夹
    v_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not v_dirs: return "Clip not found", 404

    target_v_dir = v_dirs[0]
    init_file = os.path.join(target_v_dir, 'init-stream0.m4s')
    chunks = sorted(glob.glob(os.path.join(target_v_dir, 'chunk-stream0-*.m4s')))

    def generate():
        ffmpeg = get_ffmpeg_tool('ffmpeg.exe')

        # 创建临时合并文件：M4S 是分段 MP4，直接二进制合并 init + chunks 即可被 ffmpeg 识别
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            with open(init_file, 'rb') as f: tmp.write(f.read())
            for chk in chunks[:10]:  # 预览仅取前10个分段以提速
                with open(chk, 'rb') as f: tmp.write(f.read())
            tmp_path = tmp.name

        # 使用 ffmpeg 转换为浏览器友好的 mp4 流 (faststart)
        cmd = [
            ffmpeg, '-i', tmp_path,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            'pipe:1'
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, startupinfo=get_hide_config())
        try:
            while True:
                data = proc.stdout.read(1024 * 128)
                if not data: break
                yield data
        finally:
            proc.terminate()
            if os.path.exists(tmp_path): os.remove(tmp_path)

    return Response(generate(), mimetype='video/mp4')


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
            name_parts = cid.split('_')
            steam_id = "Unknown"
            m_time = os.path.getmtime(entry)
            if len(name_parts) >= 4:
                steam_id = name_parts[1]
                date_str = name_parts[2]
                time_str = name_parts[3]
                try:
                    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                    m_time = dt.timestamp()
                except:
                    pass
            game_name = f"AppID {steam_id}"
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
                "id": cid, "game": game_name, "time": m_time,
                "is_converted": is_done, "thumb": f"/api/thumbnail/{cid}" if os.path.exists(t_path) else None,
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