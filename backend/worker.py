import os
import sys
import glob
import subprocess
import re


def get_ffmpeg_tool(name='ffmpeg.exe'):
    """适配打包路径的工具获取函数"""
    base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath(".")
    return os.path.join(base, 'bin', name)


def get_hide_config():
    """隐藏 CMD 窗口的关键配置"""
    if sys.platform.startswith('win'):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si
    return None


def get_video_duration(file_path):
    """【真实进度核心】获取视频总时长"""
    ffprobe = get_ffmpeg_tool('ffprobe.exe')
    cmd = [
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=get_hide_config())
        return float(result.stdout.strip())
    except:
        return 0


def generate_quick_thumb(folder, t_path):
    """静默生成预览图"""
    s_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not s_dirs: return
    init = os.path.join(s_dirs[0], 'init-stream0.m4s')
    chk = os.path.join(s_dirs[0], 'chunk-stream0-00001.m4s')
    tmp = t_path + ".tmp.mp4"
    ffmpeg = get_ffmpeg_tool('ffmpeg.exe')
    try:
        with open(tmp, 'wb') as f:
            with open(init, 'rb') as i: f.write(i.read())
            with open(chk, 'rb') as c: f.write(c.read())
        subprocess.run([ffmpeg, '-y', '-i', tmp, '-vframes', '1', t_path],
                       startupinfo=get_hide_config(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def convert_clip(folder, out, status):
    """【真实进度版】转码逻辑"""
    ffmpeg = get_ffmpeg_tool('ffmpeg.exe')
    s_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not s_dirs: return
    s_f = s_dirs[0]

    # 步骤 1: 二进制合并 (占 10% 进度)
    status['progress'] = 5
    status['eta'] = "正在准备流数据..."
    v_init, v_chks = os.path.join(s_f, 'init-stream0.m4s'), sorted(glob.glob(os.path.join(s_f, 'chunk-stream0-*.m4s')))
    a_init, a_chks = os.path.join(s_f, 'init-stream1.m4s'), sorted(glob.glob(os.path.join(s_f, 'chunk-stream1-*.m4s')))
    tmp_v, tmp_a = out + ".v", out + ".a"

    try:
        with open(tmp_v, 'wb') as f:
            with open(v_init, 'rb') as i: f.write(i.read())
            for c in v_chks: f.write(open(c, 'rb').read())

        has_a = False
        if os.path.exists(a_init):
            has_a = True
            with open(tmp_a, 'wb') as f:
                with open(a_init, 'rb') as i: f.write(i.read())
                for c in a_chks: f.write(open(c, 'rb').read())

        # 步骤 2: 获取总时长 (占 5% 进度)
        duration = get_video_duration(tmp_v)
        status['progress'] = 15

        # 步骤 3: 真实进度封装 (占 15%-100% 进度)
        cmd = [ffmpeg, '-y', '-i', tmp_v]
        if has_a: cmd += ['-i', tmp_a]
        cmd += ['-c', 'copy', out, '-progress', 'pipe:1', '-nostats']

        process = subprocess.Popen(
            cmd, startupinfo=get_hide_config(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8'
        )

        for line in process.stdout:
            # 记录 ffmpeg 原始消息
            status['last_raw_log'] = line.strip()

            if 'out_time_ms' in line and duration > 0:
                ms_match = re.search(r'out_time_ms=(\d+)', line)
                if ms_match:
                    curr_ms = int(ms_match.group(1))
                    curr_sec = curr_ms / 1000000.0
                    real_p = 15 + int((curr_sec / duration) * 84)
                    status['progress'] = min(real_p, 99)
                    status['eta'] = f"处理中: {int(curr_sec)}s / {int(duration)}s"

        process.wait()
        status['progress'] = 100
        status['eta'] = "转换成功"
    except Exception as e:
        status['status'] = 'error'
        status['eta'] = "转换失败"
    finally:
        for f in [tmp_v, tmp_a]:
            if os.path.exists(f): os.remove(f)