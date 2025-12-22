import os
import glob
import time
import queue
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 兼容性导入逻辑，修复 ModuleNotFoundError
try:
    from worker import convert_clip
except ImportError:
    from .worker import convert_clip

base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(base_dir)
frontend_dir = os.path.join(root_dir, 'frontend')

app = Flask(__name__, static_url_path='', static_folder=frontend_dir)
CORS(app)

CONVERSION_QUEUE = queue.Queue()
CONVERSION_STATUS = {}
CURRENT_CLIP_PATH = None

def worker_thread_func():
    while True:
        try:
            # 这里的 clip_id 是为了在状态字典中定位
            item = CONVERSION_QUEUE.get(timeout=1)
            clip_folder, output_path, clip_id = item
            CONVERSION_STATUS[clip_id]['status'] = 'running'
            convert_clip(clip_folder, output_path, CONVERSION_STATUS[clip_id])
            CONVERSION_QUEUE.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"工作线程异常: {e}")

threading.Thread(target=worker_thread_func, daemon=True).start()

@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/api/thumbnail/<clip_id>')
def get_thumbnail(clip_id):
    if CURRENT_CLIP_PATH:
        # 直接从 clips 目录下寻找对应的 jpg
        return send_from_directory(CURRENT_CLIP_PATH, f"{clip_id}.jpg")
    return "Not Found", 404

@app.route('/api/set_path', methods=['POST'])
def set_path():
    global CURRENT_CLIP_PATH
    path = request.json.get('path', '').strip()
    if path and os.path.isdir(path):
        # 尝试检测子目录 clips
        p_clips = os.path.join(path, 'clips')
        CURRENT_CLIP_PATH = p_clips if os.path.isdir(p_clips) else path
        return jsonify({"success": True, "message": f"成功! 录像位置: {CURRENT_CLIP_PATH}"})
    return jsonify({"success": False, "message": "路径无效"}), 400


try:
    from worker import convert_clip, generate_quick_thumb
except ImportError:
    from .worker import convert_clip, generate_quick_thumb


@app.route('/api/clips', methods=['GET'])
def list_clips():
    if not CURRENT_CLIP_PATH: return jsonify({"clips": []})
    clips = []
    dirs = glob.glob(os.path.join(CURRENT_CLIP_PATH, 'clip_*'))

    for d in dirs:
        if os.path.isdir(d):
            cid = os.path.basename(d)
            thumb_name = f"{cid}.jpg"
            thumb_path = os.path.join(CURRENT_CLIP_PATH, thumb_name)

            # --- 新增：如果没图，扫描时立刻生成 ---
            if not os.path.exists(thumb_path):
                generate_quick_thumb(d, thumb_path)
            # ------------------------------------

            is_done = os.path.exists(os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"))
            clips.append({
                "id": cid,
                "name": cid,
                "is_converted": is_done,
                "thumb": f"/api/thumbnail/{cid}" if os.path.exists(thumb_path) else None,
                "status": CONVERSION_STATUS.get(cid, {}).get('status', 'idle')
            })
    return jsonify({"success": True, "clips": clips})

@app.route('/api/queue', methods=['POST'])
def add_to_queue():
    clip_ids = request.json.get('clip_ids', [])
    for cid in clip_ids:
        # 避免重复加入正在运行的任务
        curr_s = CONVERSION_STATUS.get(cid, {}).get('status', 'idle')
        if curr_s in ['idle', 'error']:
            CONVERSION_STATUS[cid] = {'status': 'pending', 'progress': 0, 'eta': '排队中'}
            CONVERSION_QUEUE.put((os.path.join(CURRENT_CLIP_PATH, cid), os.path.join(CURRENT_CLIP_PATH, f"{cid}.mp4"), cid))
    return jsonify({"success": True})

@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify({"all_statuses": CONVERSION_STATUS})

if __name__ == '__main__':
    print("服务已启动: http://127.0.0.1:5000")
    app.run(debug=False, port=5000, threaded=True)