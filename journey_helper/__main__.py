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
    with open(output, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return 0


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
