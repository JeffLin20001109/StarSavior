import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

DESKTOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESKTOP))

import launcher  # noqa: E402
from journey_helper import update  # noqa: E402
from tools import package_code  # noqa: E402


def package(commit, launcher_id, built=200, files=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        for name, text in (files or {'journey_helper/__init__.py': ''}).items():
            z.writestr(name, text)
        z.writestr('manifest.json', json.dumps({'commit': commit, 'launcher': launcher_id, 'built': built}))
    data = buffer.getvalue()
    return data, {'url': 'https://example/code.zip', 'sha256': hashlib.sha256(data).hexdigest(),
                  'launcher': launcher_id, 'built': built}


class CheckTests(unittest.TestCase):
    def test_current_commit_reads_build_info(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'build_info.json'
            path.write_text('{"commit": "abc123"}', encoding='utf-8')
            self.assertEqual(update.current_commit(path), 'abc123')

    def test_current_commit_missing_means_no_check(self):
        self.assertIsNone(update.current_commit(Path('does-not-exist.json')))

    def _check(self, payload, current='old'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
        with mock.patch.object(update.net, 'get', return_value=body):
            return update.check('https://example/version.json', current)

    def test_newer_commit_is_reported(self):
        result = self._check({'commit': 'new', 'url': 'https://example/app.exe', 'code': {'url': 'u'}})
        self.assertEqual(result, {'commit': 'new', 'url': 'https://example/app.exe', 'code': {'url': 'u'}})

    def test_same_commit_is_not_reported(self):
        self.assertIsNone(self._check({'commit': 'old', 'url': 'x'}))

    def test_bad_payload_is_ignored(self):
        self.assertIsNone(self._check(b'not json'))
        self.assertIsNone(self._check({'url': 'x'}))

    def test_network_error_is_ignored(self):
        with mock.patch.object(update.net, 'get', side_effect=OSError('offline')):
            self.assertIsNone(update.check('https://example/version.json', 'old'))

    def test_no_check_without_build_info_or_url(self):
        with mock.patch.object(update.net, 'get') as get:
            self.assertIsNone(update.check('https://example/version.json', None))
            self.assertIsNone(update.check('', 'old'))
        get.assert_not_called()


class HotUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'code'
        self.launcher = {'launcher': 'L1', 'code_root': str(self.root), 'code_commit': None}

    def tearDown(self):
        self.tmp.cleanup()

    def test_needs_same_launcher(self):
        _, code = package('new', 'L1')
        self.assertTrue(update.can_hot_update({'commit': 'new', 'code': code}, self.launcher))
        self.assertFalse(update.can_hot_update({'commit': 'new', 'code': dict(code, launcher='L2')}, self.launcher))
        self.assertFalse(update.can_hot_update({'commit': 'new', 'code': None}, self.launcher))
        self.assertFalse(update.can_hot_update({'commit': 'new', 'code': code}, {}))  # 從原始碼執行

    def test_bad_version_is_not_retried(self):
        _, code = package('new', 'L1')
        self.root.mkdir(parents=True)
        (self.root / 'state.json').write_text(json.dumps({'bad': ['new']}), encoding='utf-8')
        self.assertFalse(update.can_hot_update({'commit': 'new', 'code': code}, self.launcher))

    def test_install_extracts_and_sets_current(self):
        data, code = package('new', 'L1')
        with mock.patch.object(update.net, 'get', return_value=data):
            self.assertTrue(update.install({'commit': 'new', 'code': code}, self.launcher))
        self.assertTrue((self.root / 'new' / 'journey_helper' / '__init__.py').exists())
        self.assertEqual(update.read_state(self.root)['current'], 'new')

    def test_install_rejects_wrong_hash(self):
        data, code = package('new', 'L1')
        with mock.patch.object(update.net, 'get', return_value=data + b'x'):
            with self.assertRaises(ValueError):
                update.install({'commit': 'new', 'code': code}, self.launcher)
        self.assertFalse((self.root / 'new').exists())

    def test_install_rejects_unsafe_paths(self):
        data, code = package('new', 'L1', files={'journey_helper/__init__.py': '', '../evil.py': 'x'})
        with mock.patch.object(update.net, 'get', return_value=data):
            with self.assertRaises(ValueError):
                update.install({'commit': 'new', 'code': code}, self.launcher)

    def test_install_rejects_mismatched_manifest(self):
        data, code = package('other', 'L1')
        with mock.patch.object(update.net, 'get', return_value=data):
            with self.assertRaises(ValueError):
                update.install({'commit': 'new', 'code': code}, self.launcher)


class RestartTests(unittest.TestCase):
    def test_restart_resets_pyinstaller_environment(self):
        # 沒有重設的話，新 exe 會沿用舊程序的暫存資料夾，舊程序結束時跳出刪除失敗的警告
        with mock.patch.object(update.sys, 'frozen', True, create=True), \
                mock.patch.object(update.subprocess, 'Popen') as popen:
            self.assertTrue(update.restart())
        args, kwargs = popen.call_args
        self.assertEqual(args, ([sys.executable, '--after', str(update.os.getpid())],))
        self.assertEqual(kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
        # 真的用這組參數建立 Popen 不會出錯（之前把關鍵字參數傳成位置參數）
        import inspect
        inspect.signature(update.subprocess.Popen.__init__).bind(None, *args, **kwargs)

    def test_restart_does_nothing_from_source(self):
        with mock.patch.object(update.subprocess, 'Popen') as popen:
            self.assertFalse(update.restart())
        popen.assert_not_called()


class LauncherTests(unittest.TestCase):
    """啟動器挑選程式碼包的規則。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.info = {'launcher': 'L1', 'commit': 'exe', 'built': 100}

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, commit, launcher_id='L1', built=200):
        folder = self.root / commit
        (folder / 'journey_helper').mkdir(parents=True)
        (folder / 'journey_helper' / '__init__.py').write_text('', encoding='utf-8')
        (folder / 'manifest.json').write_text(json.dumps({'commit': commit, 'launcher': launcher_id, 'built': built}))
        (self.root / 'state.json').write_text(json.dumps({'current': commit}), encoding='utf-8')

    def test_loads_newer_compatible_code(self):
        self.install('new')
        self.assertEqual(launcher._downloaded_code(self.info, self.root), (self.root / 'new', 'new'))

    def test_ignores_other_launcher(self):
        self.install('new', launcher_id='L2')
        self.assertEqual(launcher._downloaded_code(self.info, self.root), (None, None))

    def test_ignores_code_older_than_exe(self):
        self.install('old', built=50)
        self.assertEqual(launcher._downloaded_code(self.info, self.root), (None, None))

    def test_ignores_bad_version(self):
        self.install('new')
        launcher._mark_bad(self.root, 'new', RuntimeError('boom'))
        self.assertEqual(launcher._downloaded_code(self.info, self.root), (None, None))
        self.assertIn('boom', json.loads((self.root / 'state.json').read_text())['last_error'])


class PackageTests(unittest.TestCase):
    def test_package_contains_code_and_data(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'code.zip'
            meta = package_code.build('abc', out)
            with zipfile.ZipFile(out) as z:
                names = set(z.namelist())
                manifest = json.loads(z.read('manifest.json'))
                build_info = json.loads(z.read('journey_helper/build_info.json'))
            self.assertIn('journey_helper/__main__.py', names)
            self.assertIn('journey_helper/translations_zh.json', names)
            self.assertIn('journey_helper/t2s.json', names)
            self.assertEqual(manifest['commit'], 'abc')
            self.assertEqual(build_info['commit'], 'abc')
            self.assertEqual(manifest['launcher'], package_code.launcher_id())
            self.assertEqual(meta['sha256'], hashlib.sha256(out.read_bytes()).hexdigest())

    def test_launcher_id_ignores_line_endings(self):
        self.assertEqual(len(package_code.launcher_id()), 16)


if __name__ == '__main__':
    unittest.main()
