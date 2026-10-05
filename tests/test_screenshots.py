"""用真實遊戲截圖（A、B）測試 OCR、卡圖比對與整個流程。需要 rapidocr 與 opencv。"""
import unittest

from PIL import Image

from journey_helper.config import DEFAULTS
from journey_helper.data import GameData
from journey_helper.ocr import ARCANA, JOURNEY, Ocr, card_crop, find_event, scan_crop
from journey_helper.pipeline import Pipeline
from journey_helper.render import Renderer
from journey_helper.translate import Translator
from tests.helpers import FIXTURES, LocalCards, fake_translate, raw_data

OCR = Ocr()


def flat(lines):
    return '\n'.join(''.join(t for t, _ in line) for line in lines)


class ScreenshotTests(unittest.TestCase):
    def frame(self, name):
        return Image.open(FIXTURES / name).convert('RGB')

    def test_ocr_journey_event(self):
        event = find_event(OCR.read(scan_crop(self.frame('journey_event.jpg'))))
        self.assertEqual((event.kind, event.title, event.phase), (JOURNEY, '訓練的方向性', (3, 'early')))

    def test_ocr_arcana_event(self):
        event = find_event(OCR.read(scan_crop(self.frame('arcana_event.jpg'))))
        self.assertEqual((event.kind, event.title), (ARCANA, '請講關於初戀的故事'))

    def test_card_image_identifies_card(self):
        frame = self.frame('arcana_event.jpg')
        event = find_event(OCR.read(scan_crop(frame)))
        cards = LocalCards()
        card, ranked, _ = cards.best(card_crop(frame, event.label), GameData(raw_data()).cards)
        self.assertEqual(card['id'], 1, ranked)

    def pipeline(self, cards=None):
        config = dict(DEFAULTS)
        translator = Translator(config, backend=fake_translate)
        data = GameData(raw_data())
        return Pipeline(OCR, lambda: data, cards or LocalCards(),
                        lambda d: Renderer(d, translator, config), config)

    def test_pipeline_journey(self):
        result = self.pipeline().run(self.frame('journey_event.jpg'))
        text = flat(result.lines)
        self.assertTrue(result.found)
        self.assertIn('譯:훈련의 방향성', text)
        self.assertNotIn('다른 선택', text)  # 9月下旬的版本被日期過濾掉

    def test_pipeline_arcana(self):
        cards = LocalCards()
        result = self.pipeline(cards).run(self.frame('arcana_event.jpg'))
        text = flat(result.lines)
        self.assertTrue(result.found, text)
        self.assertIn('阿爾克那：譯:하늘의 시험（譯:엘리사）', text)
        self.assertIn('譯:첫사랑 얘기 해주세요', text)
        self.assertNotIn('도를 아십니까', text)  # 只顯示目前遇到的事件
        self.assertNotIn('하늘의 시험（譯:엘리사）  ', text)  # 不顯示韓文原文
        self.assertEqual(sorted(cards.calls[0]), [1, 2])  # 只比對事件名稱相符的卡

    def test_pipeline_no_event(self):
        frame = self.frame('journey_event.jpg').crop((1300, 600, 2688, 1216))
        result = self.pipeline().run(frame)
        self.assertFalse(result.found)


if __name__ == '__main__':
    unittest.main()
