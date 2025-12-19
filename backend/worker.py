import os
import glob
import re
import subprocess
import time


def get_stream_files(stream_folder, stream_index):
    """获取指定索引流的初始化文件和排序后的碎片文件"""
    init_file = os.path.join(stream_folder, f'init-stream{stream_index}.m4s')
    chunk_files = glob.glob(os.path.join(stream_folder, f'chunk-stream{stream_index}-*.m4s'))

    if not os.path.exists(init_file) or not chunk_files:
        return None, None

    def sort_key(f):
        match = re.search(rf'chunk-stream{stream_index}-(\d+)\.m4s', os.path.basename(f))
        return int(match.group(1)) if match else 0

    chunk_files.sort(key=sort_key)
    return init_file, chunk_files


def merge_files(init, chunks, output):
    """通用的二进制合并函数"""
    with open(output, "wb") as outfile:
        with open(init, "rb") as infile:
            outfile.write(infile.read())
        for chunk in chunks:
            with open(chunk, "rb") as infile:
                outfile.write(infile.read())


def convert_clip(clip_folder, output_path, status_dict):
    stream_dirs = glob.glob(os.path.join(clip_folder, 'video', 'fg_*'))
    if not stream_dirs:
        status_dict.update({'status': 'error', 'message': '未找到视频流目录'})
        return

    stream_folder = stream_dirs[0]
    v_init, v_chunks = get_stream_files(stream_folder, 0)  # Stream 0 视频
    a_init, a_chunks = get_stream_files(stream_folder, 1)  # Stream 1 音频

    if not v_init:
        status_dict.update({'status': 'error', 'message': '视频流缺失'})
        return

    temp_v = os.path.join(stream_folder, "temp_v.mp4")
    temp_a = os.path.join(stream_folder, "temp_a.mp4")

    try:
        # 1. 合并视频
        status_dict['eta'] = "正在合并视频轨..."
        merge_files(v_init, v_chunks, temp_v)
        status_dict['progress'] = 50

        # 2. 合并音频 (如果有)
        has_audio = False
        if a_init:
            status_dict['eta'] = "正在合并音频轨..."
            merge_files(a_init, a_chunks, temp_a)
            has_audio = True

        # 3. 使用 FFmpeg 混合
        status_dict['eta'] = "FFmpeg 正在封装音视频..."
        cmd = ['ffmpeg', '-y']
        cmd += ['-i', temp_v]
        if has_audio:
            cmd += ['-i', temp_a]

        # 映射流并输出
        cmd += ['-c', 'copy', output_path]

        print(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        status_dict['progress'] = 100
        status_dict['eta'] = "完成"

    except Exception as e:
        status_dict.update({'status': 'error', 'message': f"转换失败: {str(e)}"})
    finally:
        # 清理
        for f in [temp_v, temp_a]:
            if os.path.exists(f): os.remove(f)