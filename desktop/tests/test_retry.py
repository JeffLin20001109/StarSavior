import unittest
from unittest import mock

try:
    from journey_helper import app as app_module
except ImportError:  # 沒有 tkinter 的環境
    app_module = None


class FakeEvent:
    def __init__(self, owner):
        self.owner, self.waits = owner, []

    def wait(self, seconds):
        self.waits.append(seconds)
        if len(self.waits) >= 4:
            self.owner._closing = True

    def clear(self):
        pass

    def set(self):
        pass


@unittest.skipIf(app_module is None, 'tkinter not available')
class RetryTests(unittest.TestCase):
    def test_download_retries_until_success_then_reruns_scan(self):
        app = app_module.App.__new__(app_module.App)
        app.config, app.dir, app.data, app.data_status = {'data_url': 'x', 'data_max_age_hours': 12}, None, None, ''
        app._closing, app._pending_frame = False, 'frame'
        app._retry_now = FakeEvent(app)
        app.translations = mock.Mock(refresh=mock.Mock(return_value='譯文表'))
        data = mock.Mock(cards=[], journey_count=lambda: 0)
        outcomes = [RuntimeError('certificate has expired'), RuntimeError('again'), (data, '已從網站更新資料')]

        def fake_load(*args):
            outcome = outcomes.pop(0) if outcomes else (data, '使用本機資料')
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        worked = []
        app._work = worked.append
        with mock.patch.object(app_module, 'load_data', fake_load), \
                mock.patch.object(app_module.threading, 'Thread',
                                  lambda target, args, daemon: mock.Mock(start=lambda: target(*args))):
            app._load_data()
        self.assertIs(app.data, data)
        self.assertEqual(app._retry_now.waits[:3], [5, 10, 12 * 3600])
        self.assertEqual(worked, ['frame'])


if __name__ == '__main__':
    unittest.main()
