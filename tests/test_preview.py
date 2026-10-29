import io
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from backend import app as api


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FileHoldingProcess:
    """Model asynchronous termination: its Windows file lock lasts until wait()."""
    def __init__(self, cmd, *, stalled=False, finished=False):
        self.handle = open(cmd[cmd.index('-i') + 1], 'rb')
        self.stdout = io.BytesIO(b'preview-data')
        self.returncode = 0 if finished else None
        self.stalled = stalled
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        pass

    def wait(self, timeout=None):
        if self.stalled and not self.killed:
            raise subprocess.TimeoutExpired('preview', timeout)
        self.handle.close()
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True

    def release(self):
        self.handle.close()
        self.stdout.close()


class PreviewTests(unittest.TestCase):
    @contextmanager
    def source(self, *, missing_init=False):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='sce-preview-') as td:
            root = pathlib.Path(td)
            stream = root / 'clip_test' / 'video' / 'fg_test'
            stream.mkdir(parents=True)
            if not missing_init:
                (stream / 'init-stream0.m4s').write_bytes(b'init')
            (stream / 'chunk-stream0-00001.m4s').write_bytes(b'chunk')
            original = tempfile.NamedTemporaryFile
            temporary_files = []

            def create_temp(**kwargs):
                result = original(dir=root, **kwargs)
                temporary_files.append(pathlib.Path(result.name))
                return result

            with patch.object(api, 'CURRENT_CLIP_PATH', str(root)), patch.object(api.tempfile, 'NamedTemporaryFile', side_effect=create_temp):
                yield api.app.test_client(), temporary_files

    def check_process_cleanup(self, *, stalled=False, finished=False):
        processes = []

        def spawn(cmd, **kwargs):
            proc = FileHoldingProcess(cmd, stalled=stalled, finished=finished)
            processes.append(proc)
            return proc

        with self.source() as (client, paths), patch.object(api.subprocess, 'Popen', side_effect=spawn):
            response = None
            try:
                response = client.get('/api/stream/clip_test', buffered=False)
                if finished:
                    self.assertEqual(response.get_data(), b'preview-data')
                response.close()
                self.assertEqual(processes[0].returncode, 0)
                self.assertTrue(processes[0].stdout.closed)
                self.assertTrue(paths)
                self.assertTrue(all(not path.exists() for path in paths))
            finally:
                for proc in processes:
                    proc.release()
                if response is not None:
                    response.close()

    def test_early_close_waits_for_file_owner_before_deleting(self):
        self.check_process_cleanup()

    def test_normal_completion_closes_pipe_and_removes_file(self):
        self.check_process_cleanup(finished=True)

    def test_termination_timeout_kills_and_reaps_file_owner(self):
        self.check_process_cleanup(stalled=True)

    def test_failed_process_start_removes_temporary_file(self):
        with self.source() as (client, paths), patch.object(api.subprocess, 'Popen', side_effect=OSError('cannot start preview')):
            with self.assertRaisesRegex(OSError, 'cannot start preview'):
                client.get('/api/stream/clip_test')
            self.assertTrue(paths)
            self.assertTrue(all(not path.exists() for path in paths))

    def test_missing_source_init_removes_partially_written_file(self):
        with self.source(missing_init=True) as (client, paths):
            with self.assertRaises(FileNotFoundError):
                client.get('/api/stream/clip_test')
            self.assertTrue(paths)
            self.assertTrue(all(not path.exists() for path in paths))

    def test_external_delete_failure_is_logged_without_escaping_close(self):
        processes = []
        original_remove = api.os.remove

        def spawn(cmd, **kwargs):
            proc = FileHoldingProcess(cmd)
            processes.append(proc)
            return proc

        with self.source() as (client, paths), patch.object(api.subprocess, 'Popen', side_effect=spawn):
            response = client.get('/api/stream/clip_test', buffered=False)

            def busy_remove(path):
                if pathlib.Path(path) in paths:
                    raise PermissionError('external file owner')
                return original_remove(path)

            try:
                with patch.object(api.os, 'remove', side_effect=busy_remove), self.assertLogs(api.app.logger, level='WARNING'):
                    response.close()
                self.assertEqual(processes[0].returncode, 0)
                self.assertTrue(processes[0].stdout.closed)
            finally:
                for proc in processes:
                    proc.release()
                response.close()


class FolderDialogTests(unittest.TestCase):
    def test_modern_folder_picker_has_no_deprecation_log(self):
        if not hasattr(api.webview, 'FileDialog'):
            self.skipTest('Modern API not available in legacy pywebview')
        window = SimpleNamespace(create_file_dialog=lambda kind: ['chosen'] if kind == api.webview.FileDialog.FOLDER else [])
        with patch.dict(api.app.config, {'WEBVIEW_WINDOW': window}), self.assertNoLogs('pywebview', level='WARNING'):
            response = api.app.test_client().get('/api/select_folder')
        self.assertEqual(response.json, {'success': True, 'path': 'chosen'})

    def test_old_webview_folder_picker_still_works(self):
        old_webview = SimpleNamespace(FOLDER_DIALOG=20)
        window = SimpleNamespace(create_file_dialog=lambda kind: ['chosen'] if kind == 20 else [])
        with patch.object(api, 'webview', old_webview), patch.dict(api.app.config, {'WEBVIEW_WINDOW': window}):
            response = api.app.test_client().get('/api/select_folder')
        self.assertEqual(response.json, {'success': True, 'path': 'chosen'})

    def test_cancelled_folder_picker_keeps_existing_response_contract(self):
        window = SimpleNamespace(create_file_dialog=lambda kind: None)
        with patch.dict(api.app.config, {'WEBVIEW_WINDOW': window}):
            response = api.app.test_client().get('/api/select_folder')
        self.assertEqual(response.json, {'success': False, 'path': ''})


if __name__ == '__main__':
    unittest.main()
