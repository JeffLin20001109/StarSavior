"""本機 OCR（RapidOCR，內建模型，不需連網），並從畫面左上角找出事件標籤與標題。"""
import threading
from dataclasses import dataclass

from .text import norm, parse_phase

JOURNEY = 'journey'
ARCANA = 'arcana'

# 只辨識畫面左上角：事件標籤、日期都在這個範圍
SCAN_REGION = (0.0, 0.0, 0.5, 0.45)


@dataclass
class Box:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float = 1.0

    @property
    def height(self):
        return self.y1 - self.y0


@dataclass
class EventLabel:
    kind: str           # JOURNEY 或 ARCANA
    title: str          # 事件名稱（黃框）
    label: Box          # 「旅程事件」/「阿爾克那事件」（紅框）
    title_box: Box = None
    phase: tuple = None  # 遊戲內日期，例如 (3, 'early')


class Ocr:
    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()

    def _get(self):
        if self._engine is None:
            from rapidocr import RapidOCR
            self._engine = RapidOCR(params={
                'Global.log_level': 'warning',
                'EngineConfig.onnxruntime.use_cuda': False,
                'EngineConfig.onnxruntime.use_dml': False,
            })
        return self._engine

    def warm_up(self):
        with self._lock:
            self._get()

    def read(self, image):
        import numpy as np
        with self._lock:
            output = self._get()(np.asarray(image.convert('RGB')))
        boxes = []
        if output.boxes is None or output.txts is None:
            return boxes
        for points, text, score in zip(output.boxes, output.txts, output.scores):
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            boxes.append(Box(str(text), min(xs), min(ys), max(xs), max(ys), float(score)))
        boxes.sort(key=lambda b: (b.y0, b.x0))
        return boxes


def label_kind(text):
    n = norm(text)
    if '旅程事件' in n or n in ('旅程事', '程事件'):
        return JOURNEY
    # 「阿爾克那事件」：OCR 偶爾會漏字，只要有「克那」或「尔克」加「事件」即可
    if '事件' in n and ('克那' in n or '尔克' in n or '阿尔' in n):
        return ARCANA
    return None


def find_event(boxes):
    """從 OCR 結果找出事件類型、事件名稱與遊戲日期。找不到回傳 None。"""
    phase = next((p for p in (parse_phase(b.text) for b in boxes) if p), None)
    for label in boxes:
        kind = label_kind(label.text)
        if not kind:
            continue
        h = max(label.height, 1.0)
        # 標題緊接在標籤下方，左側大致對齊
        below = [b for b in boxes if b is not label
                 and label.y0 + 0.5 * h <= b.y0 <= label.y1 + 1.6 * h
                 and label.x0 - 2.5 * h <= b.x0 <= label.x0 + 4 * h
                 and len(norm(b.text)) >= 2]
        title_box = min(below, key=lambda b: b.y0) if below else None
        title = title_box.text.strip() if title_box else ''
        if not title:
            # OCR 把標籤與標題連在一起時，取「事件」後面的字
            tail = label.text.split('事件', 1)
            title = tail[1].strip() if len(tail) == 2 else ''
        if title:
            return EventLabel(kind, title, label, title_box, phase)
    return None


def scan_crop(image):
    w, h = image.size
    x0, y0, x1, y1 = SCAN_REGION
    return image.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def card_crop(image, label):
    """阿爾克那事件左側的卡片圖（B 圖黃框）。座標相對於 scan_crop 的原點，也就是整張畫面左上角。"""
    w, h = image.size
    mid = (label.y0 + label.y1) / 2
    left = max(0, int(label.x0 - 0.18 * h))
    right = max(left + 8, int(label.x0 - 0.004 * h))
    top = max(0, int(mid - 0.125 * h))
    bottom = min(h, int(mid + 0.125 * h))
    return image.crop((left, top, min(w, right), bottom))
