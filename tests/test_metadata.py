import pathlib
import queue
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend import app as api
from backend.metadata import get_clip_metadata
from backend.worker import get_ffmpeg_tool, get_hide_config


class MetadataTests(unittest.TestCase):
    def test_fragment_edges_measure_full_duration_with_offset_and_b_frames(self):
        # Four seconds over multiple fragments, starting at a large timestamp.
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td) / 'clip_test'
            streams = folder / 'video' / 'fg_test'
            streams.mkdir(parents=True)
            subprocess.run([
                get_ffmpeg_tool(), '-v', 'error', '-copyts', '-f', 'lavfi', '-i',
                'testsrc2=size=160x90:rate=25:duration=4', '-vf', 'setpts=PTS+36000/TB',
                '-c:v', 'libx264', '-g', '25', '-bf', '2', '-f', 'dash',
                '-seg_duration', '1', 'test.mpd'], cwd=streams, check=True,
                capture_output=True, startupinfo=get_hide_config(), timeout=20)
            result = get_clip_metadata(str(folder))
            self.assertAlmostEqual(result['duration_seconds'], 4, places=2)
            self.assertEqual(result['estimated_size_bytes'], sum(p.stat().st_size for p in streams.glob('*.m4s')))

    def test_missing_and_corrupt_media_are_unknown_without_losing_size(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(get_clip_metadata(td), {'duration_seconds': None, 'estimated_size_bytes': None})
            streams = pathlib.Path(td) / 'video' / 'fg_test'
            streams.mkdir(parents=True)
            for name in ['init-stream0.m4s', 'chunk-stream0-00001.m4s', 'init-stream1.m4s', 'chunk-stream1-00001.m4s']:
                (streams / name).write_bytes(b'bad')
            result = get_clip_metadata(td)
            self.assertIsNone(result['duration_seconds'])
            self.assertEqual(result['estimated_size_bytes'], 12)

    def test_route_rejects_stale_library_and_path_escape(self):
        with tempfile.TemporaryDirectory() as td, patch.object(api, 'CURRENT_CLIP_PATH', td):
            client = api.app.test_client()
            self.assertEqual(client.get('/api/metadata/clip_test?library=old').status_code, 409)
            self.assertEqual(client.get('/api/metadata/clip_..%5Coutside').status_code, 404)
            self.assertEqual(client.get('/api/metadata/clip_missing').status_code, 404)

    def test_total_keeps_finished_failed_and_requeued_attempts(self):
        states = {'clip_done': {'status': 'finished', 'elapsed_seconds': 12.5},
                  'clip_error': {'status': 'error', 'elapsed_seconds': 3},
                  'clip_pending': {'status': 'pending'}}
        with tempfile.TemporaryDirectory() as td, patch.object(api, 'CURRENT_CLIP_PATH', td), \
                patch.object(api, 'EXPORT_PATH', td), patch.object(api, 'CONVERSION_STATUS', states), \
                patch.object(api, 'CONVERSION_QUEUE', queue.Queue()), \
                patch.object(api, 'PREVIOUS_TASK_SECONDS', 0), patch.object(api, 'PYTHON_LOGS', []):
            client = api.app.test_client()
            self.assertEqual(client.get('/api/progress').json['total_elapsed_seconds'], 15.5)
            client.post('/api/queue', json={'clip_ids': ['clip_done', 'clip_done']})
            self.assertEqual(client.get('/api/progress').json['total_elapsed_seconds'], 15.5)
            states['clip_done'] = {'status': 'running', 'elapsed_seconds': 2}
            self.assertEqual(client.get('/api/progress').json['total_elapsed_seconds'], 17.5)
