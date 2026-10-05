import unittest

from journey_helper.config import DEFAULTS
from journey_helper.data import GameData
from journey_helper.matching import match_journey
from journey_helper.ocr import ARCANA, JOURNEY, Box, find_event, label_kind
from journey_helper.render import Renderer
from journey_helper.text import parse_phase, phase_zh, similarity
from journey_helper.translate import Translator
from tests.helpers import fake_translate, raw_data


def flat(lines):
    return '\n'.join(''.join(t for t, _ in line) for line in lines)


class TextTests(unittest.TestCase):
    def test_phase(self):
        self.assertEqual(parse_phase('3月上旬'), (3, 'early'))
        self.assertEqual(parse_phase('3월 초순'), (3, 'early'))
        self.assertEqual(phase_zh('12월 하순'), '12月下旬')
        self.assertIsNone(parse_phase('距離目標'))

    def test_similarity_ignores_script_and_punctuation(self):
        self.assertGreater(similarity('訓練的方向性', '训练的方向性'), 0.99)
        self.assertGreater(similarity('請講關於初戀的故事', '請講關於初戀的故事。'), 0.95)
        self.assertLess(similarity('訓練的方向性', '古代救援者的遺物'), 0.3)


class OcrLogicTests(unittest.TestCase):
    def test_label_kind(self):
        self.assertEqual(label_kind('旅程事件'), JOURNEY)
        self.assertEqual(label_kind('阿爾克那事件'), ARCANA)
        self.assertEqual(label_kind('阿尔克那事件'), ARCANA)
        self.assertIsNone(label_kind('參加評鑑戰'))

    def test_title_below_label(self):
        boxes = [Box('3月上旬', 300, 120, 450, 168), Box('阿爾克那事件', 324, 269, 508, 307),
                 Box('請講關於初戀的故事', 316, 298, 671, 362), Box('擔任臨時教師', 700, 1000, 1500, 1040)]
        event = find_event(boxes)
        self.assertEqual((event.kind, event.title, event.phase), (ARCANA, '請講關於初戀的故事', (3, 'early')))

    def test_no_event(self):
        self.assertIsNone(find_event([Box('參加評鑑戰', 0, 0, 10, 10)]))


class MatchRenderTests(unittest.TestCase):
    def setUp(self):
        self.data = GameData(raw_data())
        self.config = dict(DEFAULTS)
        self.renderer = Renderer(self.data, Translator(self.config, backend=fake_translate), self.config)

    def test_journey_phase_filter(self):
        match = match_journey(self.data, '訓練的方向性', (3, 'early'))
        self.assertEqual([v['id'] for v in match.variants], [101])
        self.assertTrue(match.phase_matched)
        self.assertEqual(len(match_journey(self.data, '訓練的方向性', None).variants), 2)

    def test_unknown_title(self):
        self.assertEqual(match_journey(self.data, '完全不存在的事件', None).variants, [])

    def test_render_translates_korean_not_site_chinese(self):
        text = flat(self.renderer.render([{'variants': match_journey(self.data, '訓練的方向性', (3, 'early')).variants}]))
        self.assertIn('譯:훈련의 방향성', text)
        self.assertIn('① 譯:1. 공격에 도움이 되는 훈련 교본', text)
        self.assertIn('譯:기초 훈련 교본 - 공격편 +1', text)
        self.assertIn('3月上旬', text)
        self.assertNotIn('基礎訓練教本', text)  # 不使用網站的中文

    def test_render_rewards(self):
        card = self.data.cards[0]
        text = flat(self.renderer.render([{'variants': [card['events'][0]]}]))
        self.assertIn('韌性 +15', text)
        self.assertIn('旅程效果「譯:번」（5 回合）', text)
        self.assertIn('耐力 +25', text)
        self.assertIn('譯:방어력이 오른다', text)
        self.assertIn('방어의 감각', text)  # 韓文原文

    def test_version_label_only_for_same_name(self):
        card = self.data.cards[0]
        text = flat(self.renderer.render([{'variants': card['events']}]))
        self.assertNotIn('版本', text)
        variants = match_journey(self.data, '訓練的方向性', None).variants
        text = flat(self.renderer.render([{'variants': variants}]))
        self.assertIn('版本 1', text)
        self.assertIn('版本 2', text)

    def test_google_response_formats(self):
        from journey_helper.translate import _parse_google
        self.assertEqual(_parse_google([[['請講', '첫', None], ['故事', '얘기', None]], None, 'ko']), '請講故事')
        self.assertEqual(_parse_google(['請講故事']), '請講故事')
        self.assertEqual(_parse_google([['請講故事', 'ko']]), '請講故事')

    def test_translation_failure_keeps_korean(self):
        def broken(text):
            raise OSError('offline')
        renderer = Renderer(self.data, Translator(self.config, backend=broken), self.config)
        lines = renderer.render([{'variants': [self.data.cards[0]['events'][1]]}])
        self.assertIn('韓文原文', flat(lines[:1]))
        self.assertIn('도를 아십니까', flat(lines))

    def test_glossary_and_replacements(self):
        config = dict(DEFAULTS, ko_glossary={'도를 아십니까': '你相信道嗎'}, zh_replacements={'譯:': '＊'})
        renderer = Renderer(self.data, Translator(config, backend=fake_translate), config)
        text = flat(renderer.render([{'variants': [self.data.cards[0]['events'][1]]}]))
        self.assertIn('你相信道嗎', text)


if __name__ == '__main__':
    unittest.main()


class BundledTranslationTests(unittest.TestCase):
    def test_bundled_table_loads_and_has_no_korean(self):
        import re

        from journey_helper.translate import load_table
        table = load_table()
        self.assertGreater(len(table), 900)
        self.assertEqual(table['훈련의 방향성'], '訓練的方向性')
        self.assertFalse([v for v in table.values() if re.search('[가-힣]', v)])

    def test_table_is_used_before_machine_translation(self):
        calls = []

        def backend(text):
            calls.append(text)
            return '機翻'
        translator = Translator(dict(DEFAULTS), backend=backend, table={'도를 아십니까': '你信「道」嗎'})
        result = translator.translate_many(['도를 아십니까', '새 문장'])
        self.assertEqual(result, {'도를 아십니까': '你信「道」嗎', '새 문장': '機翻'})
        self.assertEqual(calls, ['새 문장'])
