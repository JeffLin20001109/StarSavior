"""阿爾克那卡圖比對：把遊戲左上角的小卡圖和網站上的卡圖做 SIFT 特徵比對。"""
import hashlib
import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urljoin

import cv2
import numpy as np
from PIL import Image

from .data import fetch

log = logging.getLogger(__name__)

NORMAL_HEIGHT = 480
MIN_INLIERS = 12
_IMAGE_KEYS = ('image', 'img', 'image_url', 'imageUrl', 'thumbnail', 'icon')


def image_url(card, site_url):
    """網站的卡圖網址：優先用資料內的圖片欄位，否則依網站規則用韓文卡名組成。"""
    site = site_url.rstrip('/') + '/'
    for key in _IMAGE_KEYS:
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return urljoin(site, value.strip())
    name = card.get('name')
    name = name.get('ko-KR', '') if isinstance(name, dict) else (name or '')
    filename = re.sub(r'[\\/:*?"<>|\s]', '', name)
    if not filename:
        raise ValueError('卡片沒有名稱，無法取得卡圖')
    return site + 'images/cards/' + quote(filename, safe='') + '.webp'


def _sift():
    return cv2.SIFT_create(nfeatures=2000, contrastThreshold=0.01)


def features(image):
    gray = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
    scale = NORMAL_HEIGHT / gray.shape[0]
    size = (max(1, round(gray.shape[1] * scale)), NORMAL_HEIGHT)
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    points, descriptors = _sift().detectAndCompute(gray, None)
    coords = np.float32([p.pt for p in points]) if points else np.zeros((0, 2), np.float32)
    return coords, descriptors


def inliers(reference, query):
    """reference / query 皆為 (座標, 描述子)。回傳符合同一透視變換的配對點數。"""
    ref_pts, ref_desc = reference
    q_pts, q_desc = query
    if ref_desc is None or q_desc is None or len(ref_desc) < 2 or len(q_desc) < 2:
        return 0
    pairs = cv2.BFMatcher().knnMatch(ref_desc, q_desc, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 6:
        return 0
    src = np.float32([ref_pts[m.queryIdx] for m in good])
    dst = np.float32([q_pts[m.trainIdx] for m in good])
    matrix, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if matrix is None or mask is None:
        return 0
    return int(mask.sum())


class CardMatcher:
    def __init__(self, site_url, directory):
        self.site_url = site_url
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._memory = {}

    def _paths(self, card):
        url = image_url(card, self.site_url)
        digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]
        stem = f'{card.get("id")}-{digest}'
        return url, self.directory / (stem + '.img'), self.directory / (stem + '.npz')

    def reference(self, card):
        url, image_path, feature_path = self._paths(card)
        if url in self._memory:
            return self._memory[url]
        if feature_path.exists():
            try:
                with np.load(feature_path) as saved:
                    desc = saved['desc'] if saved['desc'].size else None
                    value = (saved['pts'], desc)
                self._memory[url] = value
                return value
            except Exception:
                pass
        if image_path.exists():
            body = image_path.read_bytes()
        else:
            body = fetch(url, timeout=15, limit=8_000_000)
            image_path.write_bytes(body)
        with Image.open(io.BytesIO(body)) as image:
            value = features(image)
        pts, desc = value
        np.savez_compressed(feature_path, pts=pts,
                            desc=desc if desc is not None else np.zeros((0, 128), np.float32))
        self._memory[url] = value
        return value

    def rank(self, crop, cards):
        """回傳 ([(配對點數, 卡片)] 由高到低, 下載失敗的卡片數)。"""
        query = features(crop)

        def score(card):
            try:
                return inliers(self.reference(card), query), card, None
            except Exception as exc:
                return 0, card, exc

        failures = 0
        ranked = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for value, card, error in pool.map(score, cards):
                if error is not None:
                    failures += 1
                    log.warning('卡圖 %s 無法使用：%s', card.get('id'), error)
                ranked.append((value, card))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked, failures

    def best(self, crop, cards):
        """只在明顯勝出時回傳卡片，否則回傳 None。"""
        ranked, failures = self.rank(crop, cards)
        if not ranked:
            return None, ranked, failures
        top = ranked[0][0]
        second = ranked[1][0] if len(ranked) > 1 else 0
        if top >= MIN_INLIERS and top >= 2 * second + 4:
            return ranked[0][1], ranked, failures
        return None, ranked, failures
