"""測試用的假資料（結構與網站 JSON 相同）。"""
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / 'shared' / 'fixtures'


def name(ko, zh, en=''):
    return {'ko-KR': ko, 'zh-TW': zh, 'en-US': en or ko, 'zh-CN': zh}


def stat(code, value):
    return {'type': 'RT_STAT', 'reward_stat': 'JST_' + code, 'min': value, 'max': value}


def raw_data():
    training = {
        'id': 101, 'name': name('훈련의 방향성', '訓練的方向性'), 'times': ['3월 초순'],
        'choices': [
            {'name': name('1. 공격에 도움이 되는 훈련 교본', '對攻擊有幫助的訓練教本'),
             'success_rewards': [[{'type': 'RT_JOURNEY_ITEM', 'reward_id': 1, 'min': 1, 'max': 1}]]},
            {'name': name('2. 생존에 도움이 되는 훈련 교본', '對生存有幫助的訓練教本'),
             'success_rewards': [[{'type': 'RT_JOURNEY_ITEM', 'reward_id': 2, 'min': 1, 'max': 1}]]},
        ],
    }
    training_late = dict(training, id=102, times=['9월 하순'],
                         choices=[{'name': name('다른 선택', '其他選項'), 'success_rewards': [[stat('POWER', 99)]]}])
    relic = {'id': 103, 'name': name('고대 구원자의 유물', '古代救援者的遺物'), 'times': ['3월 중순'],
             'choices': [{'name': {}, 'success_rewards': [[{'type': 'RT_POTEN_POINT', 'min': 10, 'max': 10}]]}]}
    first_love = {
        'id': 201, 'name': name('첫사랑 얘기 해주세요', '請講關於初戀的故事'),
        'choices': [
            {'name': name('아이들이 좋아하는 이야기를 해줘.', '講些孩子們喜歡聽的故事吧。'),
             'success_rewards': [[stat('ENDURANCE', 15)]]},
            {'name': name('단호하게 수업을 해봐.', '果斷地上課吧。'),
             'success_rewards': [[{'type': 'RT_SE_POTEN', 'reward_id': 7}],
                                 [{'type': 'RT_JOURNEY_BUFF', 'reward_id': 9, 'turn': 5}],
                                 [{'type': 'RT_STAMINA', 'min': 25, 'max': 25}],
                                 [stat('ENDURANCE', 5)]]},
        ],
    }
    dao = {'id': 202, 'name': name('도를 아십니까', '你知道道嗎'),
           'choices': [{'name': {}, 'success_rewards': [[stat('HEALTH', 5)], [stat('ENDURANCE', 10)]]}]}
    other_love = dict(first_love, id=301)
    return {
        'journeys': {'훈련의 방향성': [training, training_late], '고대 구원자의 유물': [relic]},
        'arcanas': [
            {'id': 1, 'name': name('하늘의 시험', '上天的考驗'), 'char_name': name('엘리사', '艾莉莎'), 'events': [first_love, dao]},
            {'id': 2, 'name': name('흰 달의 포옹', '白月溫煦如陽光'), 'events': [other_love]},
            {'id': 3, 'name': name('다른 카드', '其他卡片'), 'events': [dao]},
        ],
        'journey_items': [{'id': 1, 'name': name('기초 훈련 교본 - 공격편', '基礎訓練教本－攻擊篇')},
                          {'id': 2, 'name': name('기초 훈련 교본 - 생존편', '基礎訓練教本－生存篇')}],
        'potentials': [{'id': 7, 'name': name('방어의 감각', '防禦的感覺'), 'desc': name('방어력이 오른다', '防禦上升')}],
        'stat_potentials': [{'id': 8, 'name': name('x', 'x')}],
        'journey_buffs': [{'id': 9, 'name': name('번', '燒')}],
    }


def fake_translate(text):
    return '譯:' + text


class LocalCards:
    """卡圖比對時改用本機 fixture，不連網。"""
    FILES = {1: 'card_elisa.jpg', 2: 'card_ling.jpg', 3: 'card_other.jpg'}

    def __init__(self):
        from journey_helper.cards import CardMatcher, features
        from PIL import Image
        self.matcher = CardMatcher.__new__(CardMatcher)
        cache = {cid: features(Image.open(FIXTURES / f)) for cid, f in self.FILES.items()}
        self.matcher.reference = lambda card: cache[card['id']]
        self.calls = []

    def best(self, crop, cards):
        self.calls.append([c['id'] for c in cards])
        return self.matcher.best(crop, cards)
