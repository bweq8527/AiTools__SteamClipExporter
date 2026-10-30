"""任务写入／处理速率；有界区间历史保留整个处理时间范围，不持久化。"""
import math
import time


def merge_history(points):
    """合并相邻区间，按用时加权；未知值不能当作零写入。"""
    merged = []
    for index in range(0, len(points), 2):
        pair = points[index:index + 2]
        duration = sum(point['dt'] for point in pair)
        point = dict(t=pair[-1]['t'], dt=duration)
        for key in ('write_mbps', 'speed'):
            point[key] = (sum(item[key] * item['dt'] for item in pair) / duration
                          if all(item[key] is not None for item in pair) else None)
        point['disk_mbps'] = point['write_mbps']
        merged.append(point)
    return merged


class TaskMonitor:
    def __init__(self, status, started):
        self.status = status
        self.started = started
        self.stage = None
        self.previous_time = started
        self.previous_bytes = 0
        self.previous_chunks = 0
        self.status['performance_history'] = {}

    def start(self, stage):
        self.stage = stage
        self.previous_time = time.monotonic()
        self.previous_bytes = 0
        self.previous_chunks = 0
        self.status.update(disk_mbps=None, write_mbps=None, processing_speed=None,
                           speed_unit='x' if stage == 'muxing' else '个/s')

    def record(self, processed_bytes=0, completed_chunks=0, output_bytes=None, speed=None, force=False):
        now = time.monotonic()
        elapsed = now - self.previous_time
        if elapsed <= 0 or (elapsed < 0.5 and not force):
            return
        if self.stage != 'muxing':
            # 只有完整 chunk 计入处理量；init 只贡献写入量。
            rate = max(0, completed_chunks - self.previous_chunks) / elapsed
            write_bytes = processed_bytes
        else:
            rate = speed if speed is not None and math.isfinite(speed) and speed >= 0 else None
            write_bytes = output_bytes
        write_rate = (max(0, write_bytes - self.previous_bytes) / elapsed / 1_000_000
                      if write_bytes is not None and self.previous_bytes is not None else None)
        point = dict(t=now - self.started, dt=elapsed, write_mbps=write_rate,
                     disk_mbps=write_rate, speed=rate)
        history = self.status['performance_history']
        points = [*history.get(self.stage, []), point]
        # 阶段末尾可能只剩微秒，合入上一采样，避免最后一个 chunk
        # 的完成计数除以极短间隔，制造虚假的巨大个/s 峰值。
        if force and elapsed < 0.5 and len(points) > 1:
            points[-2:] = merge_history(points[-2:])
        if len(points) > 600:
            points = merge_history(points)
        self.status['performance_history'] = {**history, self.stage: points}
        # disk_mbps 保留字段名兼容，但不再包含读取量。
        self.status.update(disk_mbps=points[-1]['write_mbps'], write_mbps=points[-1]['write_mbps'], processing_speed=points[-1]['speed'],
                           speed_unit='x' if self.stage == 'muxing' else '个/s')
        self.previous_time = now
        self.previous_bytes = write_bytes
        self.previous_chunks = completed_chunks
