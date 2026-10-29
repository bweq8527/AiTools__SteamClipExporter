"""按任务记录短期性能曲线，不持久化，也不测量整块磁盘的繁忙比例。"""
import ctypes
import math
import sys
import time
from ctypes import wintypes


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        'read_operations', 'write_operations', 'other_operations',
        'read_bytes', 'write_bytes', 'other_bytes')]


def get_process_io_bytes(process):
    """FFmpeg 进程累计读写量；不支持的平台／查询失败返回未知。"""
    if not sys.platform.startswith('win') or not getattr(process, 'pid', None):
        return None
    handle = None
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IoCounters)]
        kernel.GetProcessIoCounters.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, process.pid)
        if not handle:
            return None
        counters = IoCounters()
        if kernel.GetProcessIoCounters(handle, ctypes.byref(counters)):
            return counters.read_bytes + counters.write_bytes
        return None
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return None
    finally:
        if handle:
            kernel.CloseHandle(handle)


class TaskMonitor:
    def __init__(self, status, started):
        self.status = status
        self.started = started
        self.stage = None
        self.previous_time = started
        self.previous_bytes = 0
        self.previous_io = None
        self.status['performance_history'] = {}

    def start(self, stage):
        self.stage = stage
        self.previous_time = time.monotonic()
        self.previous_bytes = 0
        self.previous_io = 0 if stage == 'muxing' else None
        self.status.update(disk_mbps=None, processing_speed=None,
                           speed_unit='x' if stage == 'muxing' else 'MB/s')

    def record(self, processed_bytes=0, io_bytes=None, speed=None, force=False):
        now = time.monotonic()
        elapsed = now - self.previous_time
        if elapsed < 0.5 and not force:
            return
        if elapsed <= 0:
            return
        if force and self.stage != 'muxing' and processed_bytes == self.previous_bytes and self.status['performance_history'].get(self.stage):
            return
        if self.stage != 'muxing':
            rate = max(0, processed_bytes - self.previous_bytes) / elapsed / 1_000_000
            disk_rate = rate * 2  # 本任务分段的读取量＋临时文件写入量。
        else:
            rate = speed if speed is not None and math.isfinite(speed) and speed >= 0 else None
            disk_rate = max(0, io_bytes - self.previous_io) / elapsed / 1_000_000 if io_bytes is not None and self.previous_io is not None else None
        point = dict(t=now - self.started, disk_mbps=disk_rate, speed=rate)
        history = self.status['performance_history']
        points = [*history.get(self.stage, []), point][-120:]
        self.status['performance_history'] = {**history, self.stage: points}
        self.status.update(disk_mbps=disk_rate, processing_speed=rate,
                           speed_unit='x' if self.stage == 'muxing' else 'MB/s')
        self.previous_time, self.previous_bytes, self.previous_io = now, processed_bytes, io_bytes
