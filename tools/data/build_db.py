"""把各來源的原始快照合併成我們自己的資料庫（給 exe 與 APK 使用）。

用法：python tools/data/build_db.py <快照資料夾 sources/> <輸出檔 journey_data.json> [報告檔 report.json]

輸出格式與 star-savior-arcana-db 的 JSON 相同（journeys、arcanas、journey_items、potentials、
stat_potentials、journey_buffs），程式不需要為了換資料來源而改寫。

合併規則（以遊戲內部編號對應兩個來源）：
- 兩站都有、選項與獎勵一致 → 用 arcana-db 的版本（有「多選一」的獎勵、韓文、繁中、遊戲內日期）。
- 兩站都有但遊戲已改版（選項或獎勵不同）→ 用 starsavior-db 的版本，選項文字相同者沿用 arcana-db 的多語系。
- 只有 starsavior-db 有 → 用 starsavior-db 的版本（只有英文，繁中名稱由我們的譯文表補上）。
- 只有 arcana-db 有 → 保留。
"""
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STARSAVIOR_DB = 'https://starsavior-db.pages.dev'
STATS = {'Strength': 'JST_POWER', 'Vitality': 'JST_HEALTH', 'Endurance': 'JST_ENDURANCE',
         'Focus': 'JST_FOCUS', 'Protection': 'JST_PROTECT'}
SIMPLE = {'PP': 'RT_POTEN_POINT', 'Stamina': 'RT_STAMINA', 'Condition': 'RT_CONDITION', 'Coins': 'RT_COIN'}
POTENTIALS = ('Standard Potential', 'Special Potential', 'Unique Potential')
MISSING_LABEL = '(Choice text missing in source data)'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def en(value):
    return value.get('en-US', '') if isinstance(value, dict) else (value or '')


def number(text):
    """'+10' → (10, 10)；'+15~+20' → (15, 20)；無法解析回傳 None。"""
    if text is None:
        return None
    parts = re.findall(r'[+-]?\d+(?:\.\d+)?', str(text))
    if not parts:
        return None
    values = [float(p) if '.' in p else int(p) for p in parts]
    return values[0], values[-1]


class References:
    """道具、潛力、旅程效果等參照表：以 arcana-db 為主，starsavior-db 才有的項目以英文名稱新增。"""

    def __init__(self, old, new_items, new_cards):
        self.tables = {name: OrderedDict((e['id'], e) for e in old[name])
                       for name in ('journey_items', 'potentials', 'stat_potentials', 'journey_buffs')}
        self.by_name = {name: {en(e.get('name')).strip().lower(): e['id'] for e in table.values() if en(e.get('name'))}
                        for name, table in self.tables.items()}
        for item in new_items:  # starsavior-db 的道具編號與 arcana-db 相同
            if item['id'] not in self.tables['journey_items'] and item.get('name'):
                self.add('journey_items', item['name'], item.get('description'), item['id'])
        for card in new_cards:
            for p in card.get('potentials') or []:
                if p.get('id') and p['id'] not in self.tables['potentials'] and p.get('category') in POTENTIALS:
                    self.add('potentials', p['name'], p.get('description'), p['id'])
        self.added = Counter()

    def add(self, table, name, description, ref_id=None):
        if ref_id is None:
            ref_id = f'sdb-{table}-{len(self.tables[table]) + 1}'
            self.added[table] += 1
        entry = {'id': ref_id, 'name': {'en-US': name}}
        if description:
            entry['desc'] = {'en-US': description}
        self.tables[table][ref_id] = entry
        self.by_name[table][name.strip().lower()] = ref_id
        return ref_id

    def find(self, table, name, description=None):
        key = (name or '').strip().lower()
        if key in self.by_name[table]:
            return self.by_name[table][key]
        return self.add(table, name, description)

    def name_of(self, table, ref_id):
        return en(self.tables[table].get(ref_id, {}).get('name')).strip().lower()


def convert_reward(r, refs):
    """starsavior-db 的一個獎勵 → arcana-db 的獎勵格式。"""
    kind, name = r.get('type'), r.get('name') or ''
    amount = number(r.get('value'))
    if kind == 'Stat':
        entry = {'type': 'RT_STAT', 'reward_stat': STATS.get(name, 'JST_' + name.upper())}
    elif kind in SIMPLE:
        entry = {'type': SIMPLE[kind]}
    elif kind == 'Item':
        entry = {'type': 'RT_JOURNEY_ITEM', 'reward_id': refs.find('journey_items', name, r.get('description'))}
        amount = amount or (1, 1)
    elif kind in POTENTIALS:
        entry = {'type': 'RT_SE_POTEN', 'reward_id': refs.find('potentials', name, r.get('description'))}
    elif kind == 'Stat Potential':
        entry = {'type': 'RT_STAT_POTEN', 'reward_id': refs.find('stat_potentials', name, r.get('description'))}
    elif kind == 'Buff':
        entry = {'type': 'RT_JOURNEY_BUFF', 'reward_id': refs.find('journey_buffs', name, r.get('description'))}
    elif kind == 'Buff Remove':
        entry = {'type': 'RT_JOURNEY_BUFF_REMOVE_NEG' if 'negative' in name.lower() else 'RT_JOURNEY_BUFF_REMOVE_POS'}
    else:
        raise ValueError(f'未知的獎勵類型：{kind}')
    if amount and entry['type'] != 'RT_STAT_POTEN':
        entry['min'], entry['max'] = amount
    return entry


def convert_condition(choice, refs):
    kind, amount, detail = choice.get('cost_type'), choice.get('cost_amount'), choice.get('cost_detail')
    if kind in (None, 'Free'):
        return None
    if kind == 'Stamina':
        return {'type': 'RR_STAMINA_USE', 'value': amount}
    if kind == 'Coins':
        return {'type': 'RR_COIN_USE', 'value': amount}
    if kind == 'PP':
        return {'type': 'RR_PP_USE', 'value': amount}
    if kind == 'Stat':
        return {'type': 'RR_STAT', 'target': STATS.get(detail, 'JST_' + str(detail).upper()), 'value': amount}
    if kind == 'Item':
        return {'type': 'RR_ITEM_USE', 'target': refs.find('journey_items', detail), 'value': amount}
    raise ValueError(f'未知的消耗類型：{kind}')


def convert_event(e, refs, old=None):
    """starsavior-db 的事件 → arcana-db 的事件格式；old 為同編號的 arcana-db 事件（借用多語系文字）。"""
    old_choices = {en(c.get('name')).strip().lower(): c for c in (old or {}).get('choices') or [] if en(c.get('name'))}
    variant = {'id': e['event_group_id'], 'name': dict(old['name']) if old else {'en-US': e['name']}, 'choices': [],
               'source': 'starsavior-db'}
    if old:
        for key in ('times', 'battle_names', 'difficulties'):
            if old.get(key):
                variant[key] = old[key]
    if e.get('scenario') and not variant.get('difficulties'):
        variant['difficulties'] = [{'en-US': e['scenario']}]
    choices = e.get('choices') or []
    for c in choices:
        label = c.get('label') or ''
        if not label and len(choices) > 1:
            label = MISSING_LABEL  # 有多個選項但來源缺少這個選項的文字；不要顯示成「無選項」
        same = old_choices.get(label.strip().lower())
        name = dict(same['name']) if same else ({'en-US': label} if label else {})
        choice = {'name': name, 'condition': convert_condition(c, refs),
                  'success_rewards': [[convert_reward(r, refs)] for r in c.get('success_rewards') or []]}
        failure = c.get('failure_rewards')
        choice['failure_rewards'] = [[convert_reward(r, refs)] for r in failure] if failure else None
        variant['choices'].append(choice)
    return variant


def same_reward(new, old, refs):
    if new.get('type') != old.get('type'):
        return False
    if new['type'] == 'RT_STAT' and new.get('reward_stat') != old.get('reward_stat'):
        return False
    if 'reward_id' in new:
        table = {'RT_JOURNEY_ITEM': 'journey_items', 'RT_SE_POTEN': 'potentials',
                 'RT_STAT_POTEN': 'stat_potentials', 'RT_JOURNEY_BUFF': 'journey_buffs'}[new['type']]
        if new['reward_id'] != old.get('reward_id') and refs.name_of(table, new['reward_id']) != refs.name_of(table, old.get('reward_id')):
            return False
    # starsavior-db 沒有數值（例如旅程效果的回合數）時不比較數值
    if 'min' in new and new['type'] != 'RT_JOURNEY_ITEM' and (new.get('min'), new.get('max')) != (old.get('min'), old.get('max')):
        return False
    return True


def compatible(converted, old, refs):
    """starsavior-db 的事件是否只是 arcana-db 事件的「簡化版」（每個獎勵都能在對應的多選一群組中找到）。"""
    a, b = converted['choices'], old.get('choices') or []
    if len(a) != len(b):
        return False
    for new_choice, old_choice in zip(a, b):
        if en(new_choice['name']).strip().lower() != en(old_choice.get('name')).strip().lower():
            return False
        if (new_choice['condition'] or None) != (old_choice.get('condition') or None):
            nc, oc = new_choice['condition'] or {}, old_choice.get('condition') or {}
            if (nc.get('type'), nc.get('value')) != (oc.get('type'), oc.get('value')):
                return False
        for key in ('success_rewards', 'failure_rewards'):
            new_groups = [g[0] for g in new_choice.get(key) or []]
            old_groups = [g for g in old_choice.get(key) or [] if isinstance(g, list)]
            if len(new_groups) != len(old_groups):
                return False
            if not all(any(same_reward(n, o, refs) for o in group) for n, group in zip(new_groups, old_groups)):
                # 順序可能不同：改用「每個新獎勵都能在某個群組找到」判斷
                if not all(any(same_reward(n, o, refs) for g in old_groups for o in g) for n in new_groups):
                    return False
    return True


def build(sources, names_zh):
    old = {name: load(sources / 'arcana-db' / f'{name}.json') for name in
           ('journeys', 'arcanas', 'journey_items', 'potentials', 'stat_potentials', 'journey_buffs')}
    new_events = load(sources / 'starsavior-db' / 'events.json')
    new_cards = load(sources / 'starsavior-db' / 'arcana.json')
    new_items = load(sources / 'starsavior-db' / 'items.json')
    refs = References(old, new_items, new_cards)
    stats = Counter()

    def merge(e, old_event):
        converted = convert_event(e, refs, old_event)
        if old_event is None:
            stats['new_only'] += 1
            return converted
        if compatible(converted, old_event, refs):
            stats['kept_arcana_db'] += 1
            return dict(old_event, source='arcana-db')
        stats['updated_from_starsavior_db'] += 1
        return converted

    # 一般旅程事件
    old_variants = {v['id']: v for group in old['journeys'].values() for v in group}
    journeys = OrderedDict()
    seen = set()
    for e in new_events:
        if e.get('type') == 'arcana':
            continue
        variant = merge(e, old_variants.get(e['event_group_id']))
        seen.add(variant['id'])
        journeys.setdefault(en(variant['name']) or str(variant['id']), []).append(variant)
    for variant in old_variants.values():
        if variant['id'] not in seen:
            stats['old_only'] += 1
            journeys.setdefault(en(variant['name']) or str(variant['id']), []).append(dict(variant, source='arcana-db'))

    # 阿爾克那卡片與事件
    old_cards = {c['id']: c for c in old['arcanas']}
    old_card_events = {ev['id']: ev for c in old['arcanas'] for ev in c.get('events') or []}
    events_by_card = {}
    for e in new_events:
        if e.get('type') == 'arcana':
            events_by_card.setdefault((e.get('arcana_name'), e.get('savior_name')), []).append(e)
    arcanas = []
    for card in new_cards:
        base = old_cards.get(card['id'])
        merged = {'id': card['id'],
                  'name': dict(base['name']) if base else {'en-US': card['arcana_name']},
                  'char_name': dict(base['char_name']) if base and base.get('char_name') else {'en-US': card['savior_name']},
                  'rarity': card.get('grade'),
                  'image': STARSAVIOR_DB + card['images']['card'] if card.get('images', {}).get('card') else None,
                  'events': []}
        chain = sorted(events_by_card.get((card['arcana_name'], card['savior_name']), []), key=lambda x: x.get('chain_index') or 0)
        for e in chain:
            merged['events'].append(merge(e, old_card_events.get(e['event_group_id'])))
        if not merged['events'] and base:
            merged['events'] = [dict(ev, source='arcana-db') for ev in base.get('events') or []]
        arcanas.append(merged)
    for card_id, base in old_cards.items():
        if card_id not in {c['id'] for c in new_cards}:
            stats['old_only_cards'] += 1
            arcanas.append(dict(base, events=[dict(ev, source='arcana-db') for ev in base.get('events') or []]))

    # 編號對不上但英文名稱相同（例如同一事件的新版本）：沿用 arcana-db 的多語系名稱
    old_names = {}
    for v in list(old_variants.values()) + list(old_card_events.values()):
        old_names.setdefault(en(v.get('name')).strip().lower(), v['name'])
    # 只有英文的事件名稱：補上我們翻譯的繁中名稱，比對遊戲畫面時使用
    missing_names = set()
    for variant in [v for g in journeys.values() for v in g] + [ev for c in arcanas for ev in c['events']]:
        name = variant['name']
        borrowed = old_names.get(en(name).strip().lower())
        if not name.get('zh-TW') and borrowed and borrowed.get('zh-TW'):
            variant['name'] = name = dict(borrowed)
            stats['names_borrowed_by_english'] += 1
        if not name.get('zh-TW'):
            if en(name) in names_zh:
                name['zh-TW'] = names_zh[en(name)]
                name['zh-TW-source'] = 'StarSavior translation'
            else:
                missing_names.add(en(name))

    data = {'journeys': journeys, 'arcanas': arcanas}
    for table, entries in refs.tables.items():
        data[table] = list(entries.values())
    stats.update({f'refs_added_{k}': v for k, v in refs.added.items()})
    report = {'stats': dict(stats), 'counts': {'journey_variants': sum(len(g) for g in journeys.values()),
                                               'journey_names': len(journeys), 'arcanas': len(arcanas),
                                               'arcana_events': sum(len(c['events']) for c in arcanas)},
              'missing_zh_names': sorted(missing_names)}
    return data, report


def main(sources, output, report_path=None):
    names_zh = load(ROOT / 'shared' / 'event_names_zh.json') if (ROOT / 'shared' / 'event_names_zh.json').exists() else {}
    data, report = build(Path(sources), names_zh)
    Path(output).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'missing_zh_names'}, ensure_ascii=False, indent=1))
    print('missing zh-TW names:', len(report['missing_zh_names']))


if __name__ == '__main__':
    main(*sys.argv[1:])
