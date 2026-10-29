import io
import pathlib
import queue
import tempfile
import unittest
from unittest.mock import patch

from backend import worker
from backend import app as api


class RecordingStatus(dict):
    def __init__(self):
        super().__init__(status='running')
        self.snapshots = []

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self.snapshots.append(dict(self))


class ExportProgressTests(unittest.TestCase):
    def run_export(self, *, audio=True, duration=4, returncode=0,
                   lines=None, output=True, missing=False, cleanup_error=False,
                   fail_second_chunk=False, broken_stdout=False):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            streams = root / 'clip' / 'video' / 'fg_test'
            streams.mkdir(parents=True)
            if not missing:
                (streams / 'init-stream0.m4s').write_bytes(b'video-init')
                (streams / 'chunk-stream0-00001.m4s').write_bytes(b'video-one')
                (streams / 'chunk-stream0-00002.m4s').write_bytes(b'video-two')
                if audio:
                    (streams / 'init-stream1.m4s').write_bytes(b'audio-init')
                    (streams / 'chunk-stream1-00001.m4s').write_bytes(b'audio-one')
            out = root / 'export.mp4'
            status = RecordingStatus()
            observations = []
            started = False

            class BrokenOutput(io.StringIO):
                def __next__(self):
                    raise OSError('stdout failed')

            class Process:
                def __init__(self):
                    self.stdout = io.StringIO(lines or 'out_time_us=2000000\nspeed=2.5x\nprogress=continue\nout_time_ms=4000000\nprogress=end\n')
                    if broken_stdout:
                        self.stdout = BrokenOutput()
                    self.returncode = None
                    self.killed = False

                def wait(self, timeout=None):
                    if broken_stdout and timeout and not self.killed:
                        raise worker.subprocess.TimeoutExpired('ffmpeg', timeout)
                    observations.append(dict(status))
                    self.returncode = returncode
                    return returncode

                def poll(self):
                    return self.returncode

                def terminate(self):
                    observations.append({'event': 'terminate'})

                def kill(self):
                    self.killed = True
                    observations.append({'event': 'kill'})

            process = Process()

            def start(cmd, **kwargs):
                nonlocal started
                started = True
                # Verify actual copied bytes, independently of telemetry counters.
                self.assertEqual(pathlib.Path(str(out) + '.v').read_bytes(), b'video-initvideo-onevideo-two')
                if audio:
                    self.assertEqual(pathlib.Path(str(out) + '.a').read_bytes(), b'audio-initaudio-one')
                if output:
                    out.write_bytes(b'output')
                return process

            def probe(path):
                observations.append(dict(status))
                return duration

            remove = worker.os.remove
            real_open = open

            def open_file(path, mode='r', *args, **kwargs):
                if fail_second_chunk and str(path).endswith('chunk-stream0-00002.m4s') and mode == 'rb':
                    raise OSError('cannot read second chunk')
                return real_open(path, mode, *args, **kwargs)

            def remove_file(path):
                if cleanup_error and str(path).endswith('.v'):
                    raise PermissionError('busy temporary file')
                remove(path)

            with patch.object(worker.subprocess, 'Popen', side_effect=start), patch.object(worker, 'get_video_duration', side_effect=probe), patch.object(worker.os, 'remove', side_effect=remove_file), patch('builtins.open', side_effect=open_file):
                worker.convert_clip(str(root / 'clip'), str(out), status)
            self.assertTrue(not started or process.stdout.closed)
            if not cleanup_error:
                self.assertFalse(pathlib.Path(str(out) + '.v').exists())
                self.assertFalse(pathlib.Path(str(out) + '.a').exists())
            return status, observations

    def test_reports_complete_chunks_for_each_track_and_all_stages(self):
        status, observations = self.run_export()
        self.assertEqual(status.get('video_done'), 2)
        self.assertEqual(status.get('video_total'), 2)
        self.assertEqual(status.get('audio_done'), 1)
        self.assertEqual(status.get('audio_total'), 1)
        stages = list(dict.fromkeys(s.get('stage') for s in status.snapshots))
        self.assertEqual(stages, ['preparing', 'joining_video', 'joining_audio', 'probing', 'muxing', 'finalizing', 'finished'])
        self.assertTrue(any(s.get('video_done') == 1 for s in status.snapshots))
        self.assertEqual(observations[0].get('stage'), 'probing')
        self.assertEqual(observations[1].get('stage'), 'finalizing')
        self.assertTrue(all(s['progress'] < 100 for s in status.snapshots[:-1]))
        self.assertEqual(status['progress'], 100)
        self.assertEqual(status['status'], 'finished')

    def test_no_audio_is_explicit_and_does_not_invent_audio_chunks(self):
        status, _ = self.run_export(audio=False)
        self.assertIs(status.get('has_audio'), False)
        self.assertEqual(status.get('audio_done'), 0)
        self.assertEqual(status.get('audio_total'), 0)
        self.assertEqual(status['status'], 'finished')

    def test_unknown_duration_still_reports_processed_time_and_speed(self):
        status, _ = self.run_export(duration=0)
        muxing = [s for s in status.snapshots if s.get('stage') == 'muxing']
        self.assertTrue(any(s.get('processed_seconds') == 2 and s.get('speed') == '2.5x' for s in muxing))
        self.assertTrue(any(s.get('progress_indeterminate') for s in muxing))
        self.assertEqual(status.get('duration_seconds'), 0)

    def test_ffmpeg_padded_speed_is_reported(self):
        status, _ = self.run_export(lines='out_time_us=2000000\nspeed=  2x\nprogress=end\n')
        self.assertEqual(status.get('speed'), '2x')

    def test_ffmpeg_scientific_speed_is_reported_and_nonfinite_is_ignored(self):
        status, _ = self.run_export(lines='speed=8.49e+03x\nprogress=continue\nspeed=1e999x\nprogress=end\n')
        self.assertEqual(status.get('speed'), '8.49e+03x')

    def test_invalid_and_negative_progress_never_produces_invalid_percentage(self):
        status, _ = self.run_export(duration=float('nan'), lines='out_time_us=N/A\nspeed=N/A\nprogress=continue\nout_time_ms=-1000\nprogress=end\n')
        self.assertEqual(status.get('processed_seconds'), 0)
        self.assertEqual(status.get('duration_seconds'), 0)
        self.assertTrue(all(0 <= s['progress'] <= 100 for s in status.snapshots))

    def test_nonzero_exit_is_error_and_never_reaches_100(self):
        status, _ = self.run_export(returncode=1)
        self.assertEqual(status['status'], 'error')
        self.assertLess(status['progress'], 100)
        self.assertIn('FFmpeg', status['eta'])
        self.assertEqual(status.get('video_done'), 2)

    def test_no_output_is_error_even_with_zero_exit(self):
        status, _ = self.run_export(output=False)
        self.assertEqual(status['status'], 'error')
        self.assertLess(status['progress'], 100)

    def test_missing_init_is_error_with_preparing_stage(self):
        status, _ = self.run_export(missing=True)
        self.assertEqual(status['status'], 'error')
        self.assertEqual(status.get('stage'), 'preparing')
        self.assertLess(status['progress'], 100)

    def test_cleanup_failure_is_visible_and_does_not_escape(self):
        status, _ = self.run_export(cleanup_error=True)
        self.assertEqual(status['status'], 'finished')
        self.assertIn('busy temporary file', status.get('cleanup_warning', ''))

    def test_partial_copy_failure_keeps_only_completed_chunk_count(self):
        status, _ = self.run_export(fail_second_chunk=True)
        self.assertEqual(status['status'], 'error')
        self.assertEqual(status.get('stage'), 'joining_video')
        self.assertEqual(status.get('video_done'), 1)
        self.assertEqual(status.get('video_total'), 2)
        self.assertIn('cannot read second chunk', status['eta'])

    def test_stdout_error_terminates_then_kills_and_preserves_error(self):
        status, observations = self.run_export(broken_stdout=True)
        self.assertEqual(status['status'], 'error')
        self.assertIn('stdout failed', status['eta'])
        self.assertEqual([s['event'] for s in observations if 'event' in s], ['terminate', 'kill'])
        self.assertEqual(status.get('cleanup_warning'), '')

    def test_missing_stream_directory_does_not_leave_running(self):
        with tempfile.TemporaryDirectory() as td:
            status = {'status': 'running'}
            worker.convert_clip(td, str(pathlib.Path(td) / 'out.mp4'), status)
            self.assertEqual(status['status'], 'error')

    def test_worker_logs_error_instead_of_success(self):
        jobs = queue.Queue()
        jobs.put(('missing-source', 'out.mp4', 'test'))
        jobs.put(None)
        statuses = {'test': {'status': 'pending'}}
        with patch.object(api, 'CONVERSION_QUEUE', jobs), patch.object(api, 'CONVERSION_STATUS', statuses), patch.object(api, 'PYTHON_LOGS', []):
            api.worker_thread()
            self.assertEqual(statuses['test']['status'], 'error')
            self.assertTrue(any('转换出错' in line for line in api.PYTHON_LOGS))
            self.assertFalse(any('转换完成' in line for line in api.PYTHON_LOGS))


if __name__ == '__main__':
    unittest.main()
