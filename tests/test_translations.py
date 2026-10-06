import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from journey_helper import translations
from journey_helper.translations import TranslationStore


class TranslationStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.bundled = self.dir / 'bundled.json'
        self.bundled.write_text(json.dumps({'가': '甲', '나': '乙'}, ensure_ascii=False), encoding='utf-8')

    def store(self):
        return TranslationStore('https://example/t.json', self.dir / 'cache', bundled=self.bundled)

    def test_download_overrides_bundled_and_is_cached(self):
        body = json.dumps({'나': '乙（新）', '다': '丙'}, ensure_ascii=False).encode('utf-8')
        store = self.store()
        table = store.table
        with mock.patch.object(translations.net, 'get', return_value=body):
            store.refresh(force=True)
        self.assertIs(store.table, table)  # 就地更新，翻譯器拿到的是同一個 dict
        self.assertEqual(table, {'가': '甲', '나': '乙（新）', '다': '丙'})
        # 下次啟動（離線）直接用本機快取
        self.assertEqual(self.store().table['다'], '丙')

    def test_failed_download_keeps_existing_table(self):
        store = self.store()
        with mock.patch.object(translations.net, 'get', side_effect=ConnectionError('offline')):
            status = store.refresh(force=True)
        self.assertEqual(store.table, {'가': '甲', '나': '乙'})
        self.assertIn('本機版本', status)

    def test_rejects_untranslated_or_invalid_payload(self):
        store = self.store()
        for payload in ([], {}, {'가': '가가', '나': '나나'}):
            with mock.patch.object(translations.net, 'get', return_value=json.dumps(payload).encode()):
                store.refresh(force=True)
        self.assertEqual(store.table, {'가': '甲', '나': '乙'})
        self.assertFalse((self.dir / 'cache' / 'translations_zh.json').exists())

    def test_wrapped_format_is_accepted(self):
        self.assertEqual(translations.parse({'version': 2, 'translations': {'가': '甲'}}), {'가': '甲'})

    def test_recent_cache_skips_download(self):
        store = self.store()
        with mock.patch.object(translations.net, 'get', return_value=b'{"x": "y"}') as get:
            store.refresh(force=True)
            store.refresh(max_age_hours=6)
        self.assertEqual(get.call_count, 1)


if __name__ == '__main__':
    unittest.main()
