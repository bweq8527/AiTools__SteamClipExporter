import os
import glob
import re
import subprocess


def get_stream_files(stream_folder, idx):
    """获取 init 和 chunk 碎片并排序"""
    init = os.path.join(stream_folder, f'init-stream{idx}.m4s')
    chunks = glob.glob(os.path.join(stream_folder, f'chunk-stream{idx}-*.m4s'))
    if not os.path.exists(init) or not chunks:
        return None, None

    def skey(f):
        m = re.search(rf'chunk-stream{idx}-(\d+)\.m4s', os.path.basename(f))
        return int(m.group(1)) if m else 0

    chunks.sort(key=skey)
    return init, chunks


def merge_bin(init, chunks, out):
    """合并二进制碎片"""
    with open(out, "wb") as f_out:
        with open(init, "rb") as f_in: f_out.write(f_in.read())
        for c in chunks:
            with open(c, "rb") as f_in: f_out.write(f_in.read())


def generate_quick_thumb(clip_folder, thumb_path):
    """在转换前，尝试从第一个分片中快速提取预览图"""
    if os.path.exists(thumb_path): return  # 已存在则跳过

    s_dirs = glob.glob(os.path.join(clip_folder, 'video', 'fg_*'))
    if not s_dirs: return

    s_folder = s_dirs[0]
    # 获取第一个分片 (chunk-stream0-00001.m4s)
    init = os.path.join(s_folder, 'init-stream0.m4s')
    first_chunk = os.path.join(s_folder, 'chunk-stream0-00001.m4s')

    if not os.path.exists(first_chunk): return

    # 临时组合极小片段用于截图
    tmp_mini = os.path.join(s_folder, "mini_thumb.tmp")
    try:
        with open(tmp_mini, "wb") as f_out:
            with open(init, "rb") as f_in: f_out.write(f_in.read())
            with open(first_chunk, "rb") as f_in: f_out.write(f_in.read())

        # FFmpeg 快速截图
        subprocess.run(['ffmpeg', '-y', '-i', tmp_mini, '-vframes', '1', thumb_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if os.path.exists(tmp_mini): os.remove(tmp_mini)

def convert_clip(clip_folder, output_path, status_dict):
    cid = os.path.basename(clip_folder)
    s_dirs = glob.glob(os.path.join(clip_folder, 'video', 'fg_*'))
    if not s_dirs:
        status_dict.update({'status': 'error', 'message': '找不到数据流'})
        return

    s_folder = s_dirs[0]
    v_init, v_chunks = get_stream_files(s_folder, 0)  # 视频
    a_init, a_chunks = get_stream_files(s_folder, 1)  # 音频

    tmp_v = os.path.join(s_folder, "v.tmp")
    tmp_a = os.path.join(s_folder, "a.tmp")

    try:
        status_dict['eta'] = "正在合并素材..."
        merge_bin(v_init, v_chunks, tmp_v)
        has_a = False
        if a_init:
            merge_bin(a_init, a_chunks, tmp_a)
            has_a = True

        status_dict['progress'] = 80
        status_dict['eta'] = "FFmpeg 封装中..."

        # FFmpeg 合并音视频
        cmd = ['ffmpeg', '-y', '-i', tmp_v]
        if has_a: cmd += ['-i', tmp_a]
        cmd += ['-c', 'copy', output_path]

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 提取第2秒预览图
        t_path = os.path.join(os.path.dirname(output_path), f"{cid}.jpg")
        subprocess.run(['ffmpeg', '-y', '-i', output_path, '-ss', '00:00:02', '-vframes', '1', t_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        status_dict['progress'] = 100
        status_dict['eta'] = "完成"
    except Exception as e:
        status_dict.update({'status': 'error', 'message': str(e)})
    finally:
        for f in [tmp_v, tmp_a]:
            if os.path.exists(f): os.remove(f)