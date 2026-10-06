import unittest
from unittest import mock

import requests

from journey_helper import net


class FakeResponse:
    def __init__(self, content=b'ok'):
        self.content = content

    def raise_for_status(self):
        pass


class NetTests(unittest.TestCase):
    def setUp(self):
        net._use_system_store = False

    def test_reuses_one_session(self):
        self.assertIs(net.session(), net.session())

    def test_falls_back_to_system_store_on_certificate_error(self):
        session = mock.Mock()
        session.request.side_effect = requests.exceptions.SSLError('certificate has expired')
        with mock.patch.object(net, 'session', return_value=session), \
                mock.patch.object(net, '_system_request', return_value=b'system') as system:
            self.assertEqual(net.get('https://example'), b'system')
            self.assertEqual(net.get('https://example'), b'system')  # 之後直接用系統憑證庫
        self.assertEqual(session.request.call_count, 1)
        self.assertEqual(system.call_count, 2)

    def test_both_stores_fail_gives_readable_error(self):
        session = mock.Mock()
        session.request.side_effect = requests.exceptions.SSLError('CERTIFICATE_VERIFY_FAILED expired')
        with mock.patch.object(net, 'session', return_value=session), \
                mock.patch.object(net, '_system_request', side_effect=OSError('CERTIFICATE_VERIFY_FAILED')):
            with self.assertRaises(ConnectionError) as caught:
                net.get('https://example')
        self.assertIn('日期時間', str(caught.exception))

    def test_size_limit(self):
        session = mock.Mock()
        session.request.return_value = FakeResponse(b'x' * 10)
        with mock.patch.object(net, 'session', return_value=session):
            with self.assertRaises(ValueError):
                net.get('https://example', limit=5)


if __name__ == '__main__':
    unittest.main()
