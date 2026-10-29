import json
import pathlib
import queue
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend import app as api
from backend.worker import convert_clip, get_ffmpeg_tool, get_hide_config


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ExportPathTests(unittest.TestCase):
    def test_change_export_directory_without_rescanning(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='sce-test-') as td:
            root = pathlib.Path(td)
            source, first, second = [root / n for n in ('source', 'first', 'second')]
            for p in (source, first, second):
                p.mkdir()
            jobs = queue.Queue()
            with patch.object(api, 'CONVERSION_QUEUE', jobs), patch.object(api, 'CONVERSION_STATUS', {}), patch.object(api, 'CURRENT_CLIP_PATH', None), patch.object(api, 'EXPORT_PATH', None), patch.object(api, 'PYTHON_LOGS', []):
                client = api.app.test_client()
                self.assertEqual(client.post('/api/set_path', json={'path': str(source), 'export_path': str(first)}).status_code, 200)
                client.post('/api/queue', json={'clip_ids': ['clip_first']})
                response = client.post('/api/set_export_path', json={'export_path': str(second)})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['export_path'], str(second))
                client.post('/api/queue', json={'clip_ids': ['clip_second']})
                self.assertEqual(jobs.get_nowait()[1], str(first / 'clip_first.mp4'))
                self.assertEqual(jobs.get_nowait()[1], str(second / 'clip_second.mp4'))
                self.assertEqual(api.CURRENT_CLIP_PATH, str(source))
                response = client.post('/api/set_export_path', json={'export_path': str(root / 'missing')})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(api.EXPORT_PATH, str(second))
                response = client.post('/api/set_export_path', json={'export_path': ''})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(api.EXPORT_PATH, str(source))

    def test_choose_output_before_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='sce-test-') as td:
            with patch.object(api, 'CURRENT_CLIP_PATH', None), patch.object(api, 'EXPORT_PATH', None), patch.object(api, 'PYTHON_LOGS', []):
                response = api.app.test_client().post('/api/set_export_path', json={'export_path': td})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(api.EXPORT_PATH, td)


@unittest.skipUnless((ROOT / 'bin/ffmpeg.exe').exists() and (ROOT / 'bin/ffprobe.exe').exists(), 'Requires local bin FFmpeg/FFprobe')
class MediaSyncTests(unittest.TestCase):
    def run_tool(self, name, args, **kwargs):
        return subprocess.run([get_ffmpeg_tool(name), '-v', 'error', *args], capture_output=True, text=True, startupinfo=get_hide_config(), check=True, **kwargs)

    def packets(self, path):
        data = json.loads(self.run_tool('ffprobe.exe', ['-show_streams', '-show_packets', '-of', 'json', str(path)]).stdout)
        return {s['codec_type']: [float(p['pts_time']) for p in data['packets'] if p['stream_index'] == s['index']] for s in data['streams']}

    def make_clip(self, root, video_start=100, audio_start=100.75, bframes=0):
        folder = root / 'clip_test'
        streams = folder / 'video' / 'fg_test'
        streams.mkdir(parents=True)
        args = ['-copyts', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=25:duration=4']
        if audio_start is not None:
            args += ['-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000:duration=4']
        args += ['-vf', f'setpts=PTS+{video_start}/TB', '-c:v', 'libx264', '-g', '25', '-bf', str(bframes)]
        if audio_start is not None:
            args += ['-af', f'asetpts=PTS+{audio_start}/TB', '-c:a', 'aac']
        self.run_tool('ffmpeg.exe', [*args, '-f', 'dash', '-seg_duration', '1', 'test.mpd'], cwd=streams)
        return folder, streams

    def assert_timeline_preserved(self, video_start, audio_start, bframes=0):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='sce-test-') as td:
            root = pathlib.Path(td)
            folder, streams = self.make_clip(root, video_start, audio_start, bframes)
            source = {}
            for i in range(1 if audio_start is None else 2):
                merged = root / f'source-{i}.mp4'
                merged.write_bytes((streams / f'init-stream{i}.m4s').read_bytes() + b''.join(p.read_bytes() for p in sorted(streams.glob(f'chunk-stream{i}-*.m4s'))))
                source.update(self.packets(merged))
            out = root / 'export.mp4'
            status = {'status': 'running'}
            convert_clip(str(folder), str(out), status)
            self.assertEqual(status['status'], 'finished', status)
            actual = self.packets(out)
            self.assertEqual(set(actual), set(source))
            # A single common shift must explain every packet in both tracks.
            shift = actual['video'][0] - source['video'][0]
            for kind, timestamps in source.items():
                self.assertEqual(len(actual[kind]), len(timestamps))
                for before, after in zip(timestamps, actual[kind]):
                    self.assertAlmostEqual(after - before, shift, delta=0.002, msg=f'{kind} timeline changed')
            self.assertLess(min(min(p) for p in actual.values()), 0.1)
            self.assertFalse(pathlib.Path(str(out) + '.v').exists())
            self.assertFalse(pathlib.Path(str(out) + '.a').exists())
            self.run_tool('ffmpeg.exe', ['-xerror', '-i', str(out), '-f', 'null', '-'])

    def test_audio_starts_later(self):
        self.assert_timeline_preserved(100, 100.75)

    def test_audio_starts_earlier(self):
        self.assert_timeline_preserved(100, 99.5)

    def test_large_timestamps_and_bframes(self):
        self.assert_timeline_preserved(36000, 36000.75, bframes=2)

    def test_video_without_audio(self):
        self.assert_timeline_preserved(100, None)

    def test_progress_reports_elapsed_media_time(self):
        times = []

        class RecordingStatus(dict):
            def __setitem__(self, key, value):
                super().__setitem__(key, value)
                if key == 'last_raw_log' and value.startswith('out_time_ms='):
                    times.append(int(value.split('=')[1]) / 1_000_000)

        with tempfile.TemporaryDirectory(dir=ROOT, prefix='sce-test-') as td:
            root = pathlib.Path(td)
            folder, _ = self.make_clip(root, 36000, 36000.75)
            status = RecordingStatus(status='running')
            convert_clip(str(folder), str(root / 'export.mp4'), status)
            self.assertEqual(status['status'], 'finished')
            self.assertTrue(any(3 < value < 6 for value in times), times)


if __name__ == '__main__':
    unittest.main()
