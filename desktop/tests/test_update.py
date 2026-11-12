import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from journey_helper import update


class UpdateCheckTests(unittest.TestCase):
    def test_current_commit_reads_build_info(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'build_info.json'
            path.write_text('{"commit": "abc123"}', encoding='utf-8')
            self.assertEqual(update.current_commit(path), 'abc123')

    def test_current_commit_missing_means_no_check(self):
        self.assertIsNone(update.current_commit(Path('does-not-exist.json')))

    def _check(self, payload, current='old'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode('utf-8')
        with mock.patch.object(update.net, 'get', return_value=body) as get:
            result = update.check('https://example/version.json', current)
        return result, get

    def test_newer_commit_is_reported(self):
        result, _ = self._check({'commit': 'new', 'url': 'https://example/app.exe'})
        self.assertEqual(result, {'commit': 'new', 'url': 'https://example/app.exe'})

    def test_same_commit_is_not_reported(self):
        result, _ = self._check({'commit': 'old', 'url': 'x'})
        self.assertIsNone(result)

    def test_bad_payload_is_ignored(self):
        self.assertIsNone(self._check(b'not json')[0])
        self.assertIsNone(self._check({'url': 'x'})[0])

    def test_network_error_is_ignored(self):
        with mock.patch.object(update.net, 'get', side_effect=OSError('offline')):
            self.assertIsNone(update.check('https://example/version.json', 'old'))

    def test_no_check_without_build_info_or_url(self):
        with mock.patch.object(update.net, 'get') as get:
            self.assertIsNone(update.check('https://example/version.json', None))
            self.assertIsNone(update.check('', 'old'))
        get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
