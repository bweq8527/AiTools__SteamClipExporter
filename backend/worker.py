import os
import sys
import glob
import re
import subprocess


def get_ffmpeg_path():
    """获取内置 FFmpeg 路径"""
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, 'bin', 'ffmpeg.exe')


def generate_quick_thumb(folder, t_path):
    """快速生成预览图"""
    s_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not s_dirs: return
    init = os.path.join(s_dirs[0], 'init-stream0.m4s')
    chk = os.path.join(s_dirs[0], 'chunk-stream0-00001.m4s')
    if not os.path.exists(chk): return

    tmp = t_path + ".tmp.mp4"
    ffmpeg = get_ffmpeg_path()
    try:
        with open(tmp, 'wb') as f:
            with open(init, 'rb') as i: f.write(i.read())
            with open(chk, 'rb') as c: f.write(c.read())
        subprocess.run([ffmpeg, '-y', '-i', tmp, '-vframes', '1', t_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def convert_clip(folder, out, status):
    ffmpeg = get_ffmpeg_path()
    s_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not s_dirs: return
    s_f = s_dirs[0]

    # 视频和音频流
    v_init = os.path.join(s_f, 'init-stream0.m4s')
    v_chks = sorted(glob.glob(os.path.join(s_f, 'chunk-stream0-*.m4s')))
    a_init = os.path.join(s_f, 'init-stream1.m4s')
    a_chks = sorted(glob.glob(os.path.join(s_f, 'chunk-stream1-*.m4s')))

    tmp_v, tmp_a = out + ".v", out + ".a"
    try:
        status['eta'] = "读取流数据..."
        with open(tmp_v, 'wb') as f:
            with open(v_init, 'rb') as i: f.write(i.read())
            for c in v_chks:
                with open(c, 'rb') as ci: f.write(ci.read())

        has_a = False
        if os.path.exists(a_init):
            has_a = True
            with open(tmp_a, 'wb') as f:
                with open(a_init, 'rb') as i: f.write(i.read())
                for c in a_chks:
                    with open(c, 'rb') as ci: f.write(ci.read())

        status['progress'] = 80
        status['eta'] = "封装 MP4..."
        cmd = [ffmpeg, '-y', '-i', tmp_v]
        if has_a: cmd += ['-i', tmp_a]
        cmd += ['-c', 'copy', out]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        status['progress'] = 100
        status['eta'] = "成功"
    except Exception as e:
        status['status'] = 'error'
        status['message'] = str(e)
    finally:
        for f in [tmp_v, tmp_a]:
            if os.path.exists(f): os.remove(f)