"""按需读取录像信息，不拼接整段录像或改变素材。"""
import glob
import json
import math
import os
import shutil
import subprocess
import tempfile

try:
    from backend.worker import get_ffmpeg_tool, get_hide_config
except ImportError:
    from worker import get_ffmpeg_tool, get_hide_config


def get_clip_metadata(folder):
    result = {'duration_seconds': None, 'estimated_size_bytes': None}
    groups = glob.glob(os.path.join(folder, 'video', 'fg_*'))
    if not groups:
        return result
    group = groups[0]
    init = os.path.join(group, 'init-stream0.m4s')
    chunks = sorted(glob.glob(os.path.join(group, 'chunk-stream0-*.m4s')))
    if not os.path.isfile(init) or not chunks:
        return result
    try:
        files = [init, *chunks]
        audio_init = os.path.join(group, 'init-stream1.m4s')
        if os.path.isfile(audio_init):
            files += [audio_init, *glob.glob(os.path.join(group, 'chunk-stream1-*.m4s'))]
        result['estimated_size_bytes'] = sum(os.path.getsize(path) for path in files)
    except OSError:
        pass
    try:
        # 首尾 fragment 含原始时间戳；无需读取中间所有媒体。关闭文件再交给 Windows 子进程。
        with tempfile.TemporaryDirectory(prefix='sce-metadata-') as temporary:
            sample = os.path.join(temporary, 'edges.mp4')
            edges = [chunks[0]] if len(chunks) == 1 else [chunks[0], chunks[-1]]
            with open(sample, 'wb') as target:
                for path in [init, *edges]:
                    with open(path, 'rb') as source:
                        shutil.copyfileobj(source, target, 1024 * 1024)
            probe = subprocess.run(
                [get_ffmpeg_tool('ffprobe.exe'), '-v', 'error', '-select_streams', 'v:0',
                 '-show_packets', '-show_entries', 'packet=pts_time,duration_time',
                 '-of', 'json', sample],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                startupinfo=get_hide_config(), check=True)
            packets = json.loads(probe.stdout).get('packets', [])
            spans = []
            for packet in packets:
                try:
                    start = float(packet['pts_time'])
                    duration = float(packet.get('duration_time', 0))
                    if math.isfinite(start) and math.isfinite(duration) and duration >= 0:
                        spans.append((start, start + duration))
                except (ValueError, TypeError, KeyError):
                    continue
            if spans:
                duration = max(end for _, end in spans) - min(start for start, _ in spans)
                if duration > 0 and math.isfinite(duration):
                    result['duration_seconds'] = duration
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        pass
    return result
