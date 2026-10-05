import ssl
import unittest
from unittest import mock
from urllib.error import URLError

from journey_helper import net


def expired():
    return URLError(ssl.SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired'))


class NetTests(unittest.TestCase):
    def setUp(self):
        net._preferred = None

    def test_falls_back_to_next_certificate_store(self):
        calls = []

        def fake(request, timeout, context):
            calls.append(context)
            if len(calls) == 1:
                raise expired()
            return 'ok'

        with mock.patch.object(net, 'urlopen', fake):
            self.assertEqual(net.open_url('https://example', 5), 'ok')
        self.assertEqual(len(calls), 2)
        self.assertEqual(net._preferred, 'system')

    def test_all_stores_fail_gives_readable_error(self):
        with mock.patch.object(net, 'urlopen', mock.Mock(side_effect=expired())):
            with self.assertRaises(ConnectionError) as caught:
                net.open_url('https://example', 5)
        self.assertIn('日期時間', str(caught.exception))

    def test_non_certificate_errors_are_not_retried(self):
        fake = mock.Mock(side_effect=URLError('timed out'))
        with mock.patch.object(net, 'urlopen', fake):
            with self.assertRaises(URLError):
                net.open_url('https://example', 5)
        self.assertEqual(fake.call_count, 1)

    def test_certifi_is_tried_first(self):
        names = [name for name, _ in net._contexts()]
        self.assertEqual(names, ['certifi', 'system'])


if __name__ == '__main__':
    unittest.main()
