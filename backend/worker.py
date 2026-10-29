import os
import sys
import glob
import subprocess
import re
import math

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
    """按阶段报告进度；分段完整复制后才增加计数，保留两轨时间轴。"""
    ffmpeg = get_ffmpeg_tool('ffmpeg.exe')
    tmp_v, tmp_a = out + ".v", out + ".a"
    process = None
    temporary_files = []
    status.update(status='running', stage='preparing', progress=0,
                  eta='正在检查素材分段', video_done=0, video_total=0,
                  audio_done=0, audio_total=0, has_audio=None,
                  processed_seconds=0, duration_seconds=0, speed=None,
                  progress_indeterminate=True, cleanup_warning='')
    try:
        s_dirs = glob.glob(os.path.join(folder, 'video', 'fg_*'))
        if not s_dirs:
            raise ValueError('未找到录像流目录')
        s_f = s_dirs[0]
        v_init = os.path.join(s_f, 'init-stream0.m4s')
        a_init = os.path.join(s_f, 'init-stream1.m4s')
        v_chks = sorted(glob.glob(os.path.join(s_f, 'chunk-stream0-*.m4s')))
        a_chks = sorted(glob.glob(os.path.join(s_f, 'chunk-stream1-*.m4s')))
        has_a = os.path.exists(a_init)
        status.update(video_total=len(v_chks), audio_total=len(a_chks), has_audio=has_a)
        if not v_chks or (has_a and not a_chks) or (a_chks and not has_a):
            raise ValueError('音视频分段或初始化文件不完整')
        sources = [v_init, *v_chks] + ([a_init, *a_chks] if has_a else [])
        sizes = [os.path.getsize(path) for path in sources]
        if any(size == 0 for size in sizes):
            raise ValueError('素材包含空的初始化文件或分段')
        total_bytes, copied_bytes = sum(sizes), 0
        tracks = [('video', v_init, v_chks, tmp_v)]
        if has_a:
            tracks.append(('audio', a_init, a_chks, tmp_a))
        for kind, init, chunks, target in tracks:
            label = '视频' if kind == 'video' else '音频'
            status.update(stage=f'joining_{kind}', eta=f'正在拼接{label}分段', progress_indeterminate=False)
            with open(target, 'wb') as merged:
                temporary_files.append(target)
                for index, source in enumerate([init, *chunks]):
                    with open(source, 'rb') as segment:
                        while True:
                            block = segment.read(1024 * 1024)
                            if not block:
                                break
                            merged.write(block)
                            copied_bytes += len(block)
                            # 0–40% 按字节估算；init 不计入完成的 chunk 数。
                            status.update(progress=min(40, int(copied_bytes / total_bytes * 40)))
                    if index:
                        status.update(**{f'{kind}_done': index})

        status.update(stage='probing', progress=40, eta='正在读取媒体时长', progress_indeterminate=True)
        duration = get_video_duration(tmp_v)
        if not math.isfinite(duration) or duration <= 0:
            duration = 0
        status.update(stage='muxing', duration_seconds=duration,
                      eta='正在封装 MP4', progress_indeterminate=duration == 0)

        # 音频以视频的起始时间为参考，保留两路分段的相对偏移。
        # 不直接 copyts：大源时间戳会使 FFmpeg 的进度时间保持为零。
        cmd = [ffmpeg, '-y', '-i', tmp_v]
        if has_a: cmd += ['-isync', '0', '-i', tmp_a]
        # 在输出端统一平移所有轨道，去除长时间轴起点且保留相对时间。
        cmd += ['-c', 'copy', '-avoid_negative_ts', 'make_zero', out, '-progress', 'pipe:1', '-nostats']

        process = subprocess.Popen(
            cmd, startupinfo=get_hide_config(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8'
        )

        with process.stdout:
            for line in process.stdout:
                status['last_raw_log'] = line.strip()
                key, _, value = line.strip().partition('=')
                value = value.strip()
                if key in ('out_time_us', 'out_time_ms') and re.fullmatch(r'-?\d+', value):
                    # FFmpeg 的旧字段 out_time_ms 实际同样以微秒计。
                    seconds = max(status['processed_seconds'], int(value) / 1000000.0, 0)
                    progress = min(98, 40 + int(seconds / duration * 58)) if duration else 40
                    status.update(processed_seconds=seconds, progress=progress)
                elif key == 'speed' and re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?x', value) and math.isfinite(float(value[:-1])):
                    status.update(speed=value)
                elif key == 'progress' and value == 'end':
                    status.update(stage='finalizing', progress=99, eta='正在完成写入并确认结果', progress_indeterminate=True)

        status.update(stage='finalizing', progress=99, eta='正在完成写入并确认结果', progress_indeterminate=True)
        if process.wait() != 0:
            raise RuntimeError('FFmpeg 封装失败，请查看 FFmpeg 日志')
        if not os.path.isfile(out) or os.path.getsize(out) == 0:
            raise RuntimeError('FFmpeg 未生成有效的非空输出文件')
    except Exception as e:
        status.update(status='error', eta=f'出错: {str(e)}', progress_indeterminate=False)
    finally:
        # 异常读取 stdout 时也必须等进程退出后再清理 Windows 输入文件。
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            except Exception as e:
                status['cleanup_warning'] = str(e)
        for path in temporary_files:
            try:
                if os.path.exists(path): os.remove(path)
            except OSError as e:
                status['cleanup_warning'] += f' {os.path.basename(path)}: {e}'
    if status['status'] != 'error':
        status.update(status='finished', stage='finished', progress=100,
                      eta='转换完成', progress_indeterminate=False)
