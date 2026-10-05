"""程式進入點。

一般使用：直接執行（雙擊 exe）。
自我檢查：StarSaviorJourneyHelper.exe --self-test 輸出.json 截圖1 [截圖2 ...]
         只做 OCR 與事件判斷，用來確認打包後的 OCR 模型可以正常使用。
"""
import json
import logging
import sys


def setup_logging():
    from .config import app_dir
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[logging.FileHandler(app_dir() / 'helper.log', encoding='utf-8', mode='w')],
    )


def self_test(output, images):
    from PIL import Image

    from .ocr import Ocr, find_event, scan_crop
    ocr = Ocr()
    report = []
    for path in images:
        boxes = ocr.read(scan_crop(Image.open(path).convert('RGB')))
        event = find_event(boxes)
        report.append({'image': path, 'texts': [b.text for b in boxes],
                       'kind': event.kind if event else None, 'title': event.title if event else None,
                       'phase': list(event.phase) if event and event.phase else None})
    import cv2  # 確認 OpenCV（卡圖比對）可以載入
    report.append({'opencv': cv2.__version__, 'sift': cv2.SIFT_create() is not None})
    report.append(network_check())
    with open(output, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return 0


def network_check():
    """實際連線網站：確認 HTTPS 憑證可用，並用真實資料跑一次比對與排版（翻譯關閉）。"""
    import tempfile

    import certifi

    from . import data as data_module
    from .config import DEFAULTS
    from .matching import match_journey
    from .render import Renderer
    from .translate import Translator
    result = {'certifi': certifi.where()}
    try:
        with tempfile.TemporaryDirectory() as folder:
            game, status = data_module.load(DEFAULTS['site_url'], folder, force=True)
        config = dict(DEFAULTS, translator='none')
        match = match_journey(game, '訓練的方向性', (3, 'early'))
        lines = Renderer(game, Translator(config), config).render([{'variants': match.variants}])
        card = game.cards[0] if game.cards else {}
        arcana = Renderer(game, Translator(config), config).render([{'variants': card.get('events', [])[:2]}])
        result.update(ok=True, status=status, journeys=game.journey_count(), cards=len(game.cards),
                      sample_score=match.score,
                      sample=[''.join(t for t, _ in line) for line in lines][:20],
                      card_keys=sorted(card), arcana_sample=[''.join(t for t, _ in line) for line in arcana][:20])
    except Exception as exc:
        result.update(ok=False, error=f'{type(exc).__name__}: {exc}')
        return result
    try:
        from .cards import CardMatcher, image_url
        with tempfile.TemporaryDirectory() as folder:
            points, _ = CardMatcher(DEFAULTS['site_url'], folder).reference(card)
        result.update(card_image=image_url(card, DEFAULTS['site_url']), card_image_features=len(points))
    except Exception as exc:
        result.update(card_image_error=f'{type(exc).__name__}: {exc}')
    try:
        translator = Translator(dict(DEFAULTS))
        result.update(translation=translator.translate_many(['첫사랑 얘기 해주세요']), translation_failed=translator.failed)
    except Exception as exc:
        result.update(translation_error=f'{type(exc).__name__}: {exc}')
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == '--self-test':
        return self_test(argv[1], argv[2:])
    from . import winapi
    winapi.set_dpi_aware()
    setup_logging()
    if not winapi.single_instance():
        import tkinter.messagebox
        tkinter.messagebox.showinfo('旅程助手', '旅程助手已經在執行中。\n右鍵點遊戲畫面上的「旅」按鈕可以結束。')
        return 0
    from .app import App
    App().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
