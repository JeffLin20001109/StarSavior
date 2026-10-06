"""懸浮按鈕與結果小窗（tkinter）。

左鍵點按鈕：辨識遊戲畫面；拖曳按鈕：移動位置；右鍵點按鈕：結束程式。
"""
import logging
import os
import queue
import threading
import time
import tkinter as tk

from . import winapi
from .cards import CardMatcher
from .config import Config, app_dir
from .data import load as load_data
from .ocr import Ocr
from .pipeline import Pipeline, Result
from .render import Renderer
from .translate import Translator
from .translations import TranslationStore

log = logging.getLogger(__name__)

FONT = 'Microsoft JhengHei UI'
TRANSPARENT = '#010203'
COLORS = {'ready': '#3b6fd8', 'busy': '#e08a1e', 'waiting': '#8a8f99'}
STYLES = {
    'h1': dict(font=(FONT, 13, 'bold'), foreground='#1d3f8f', spacing1=6),
    'h2': dict(font=(FONT, 12, 'bold'), foreground='#6a3fb5', spacing1=4),
    'choice': dict(font=(FONT, 11, 'bold'), foreground='#0b6e4f', spacing1=5),
    'effect': dict(font=(FONT, 11), foreground='#202020'),
    'note': dict(font=(FONT, 10), foreground='#4a4f57'),
    'warn': dict(font=(FONT, 10), foreground='#b3261e'),
    'dim': dict(font=(FONT, 9), foreground='#5f6670'),
    'special': dict(font=(FONT, 11), foreground='#9a7400'),
    'minus': dict(font=(FONT, 11), foreground='#c62828'),
}


class FloatingButton:
    def __init__(self, app, size):
        self.app = app
        self.size = size
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=TRANSPARENT)
        try:
            self.win.attributes('-transparentcolor', TRANSPARENT)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, width=size, height=size, bg=TRANSPARENT,
                                highlightthickness=0, cursor='hand2')
        self.canvas.pack()
        pad = max(2, size // 16)
        self.circle = self.canvas.create_oval(pad, pad, size - pad, size - pad, fill=COLORS['waiting'],
                                              outline='white', width=max(2, size // 20))
        self.label = self.canvas.create_text(size / 2, size / 2, text='旅', fill='white',
                                             font=(FONT, max(10, int(size / 3.2)), 'bold'))
        self.canvas.bind('<ButtonPress-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._motion)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<ButtonPress-3>', lambda e: app.quit())
        self._drag = None
        self.shown = True
        self.win.update_idletasks()
        winapi.make_no_activate(self.win)

    def set_state(self, state):
        self.canvas.itemconfigure(self.circle, fill=COLORS[state])
        self.canvas.itemconfigure(self.label, text='…' if state == 'busy' else '旅')

    def move(self, x, y):
        self.win.geometry(f'{self.size}x{self.size}+{int(x)}+{int(y)}')

    def show(self, visible):
        if visible and not self.shown:
            self.win.deiconify()
            self.win.attributes('-topmost', True)
        elif not visible and self.shown:
            self.win.withdraw()
        self.shown = visible

    def position(self):
        return self.win.winfo_x(), self.win.winfo_y()

    def _press(self, event):
        self._drag = (event.x_root, event.y_root, self.win.winfo_x(), self.win.winfo_y(), False)

    def _motion(self, event):
        if not self._drag:
            return
        sx, sy, wx, wy, moved = self._drag
        dx, dy = event.x_root - sx, event.y_root - sy
        if moved or abs(dx) + abs(dy) > 5:
            self._drag = (sx, sy, wx, wy, True)
            self.move(wx + dx, wy + dy)

    def _release(self, event):
        drag, self._drag = self._drag, None
        if drag and drag[4]:
            self.app.button_dragged()
        else:
            self.app.scan()


class Popup:
    def __init__(self, app, scale):
        self.app = app
        self.scale = scale
        self.width = int(470 * scale)
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.configure(bg='#3b6fd8')
        header = tk.Frame(self.win, bg='#3b6fd8')
        header.pack(fill='x')
        self.title = tk.Label(header, text='', bg='#3b6fd8', fg='white', font=(FONT, 11, 'bold'), anchor='w')
        self.title.pack(side='left', padx=8, pady=3, fill='x', expand=True)
        close = tk.Label(header, text=' ✕ ', bg='#3b6fd8', fg='white', font=(FONT, 11, 'bold'), cursor='hand2')
        close.pack(side='right', padx=2)
        close.bind('<Button-1>', lambda e: self.hide())
        for widget in (header, self.title):
            widget.bind('<ButtonPress-1>', self._press)
            widget.bind('<B1-Motion>', self._motion)
        body = tk.Frame(self.win, bg='white')
        body.pack(fill='both', expand=True, padx=2, pady=(0, 2))
        self.text = tk.Text(body, wrap='char', bg='white', relief='flat', padx=10, pady=8,
                            cursor='arrow', highlightthickness=0, borderwidth=0)
        bar = tk.Scrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)
        for name, options in STYLES.items():
            self.text.tag_configure(name, **options)
        self.win.bind_all('<MouseWheel>', self._wheel)
        self._drag = None
        self.visible = False
        self._hidden_by_game = False
        self.win.withdraw()
        self.win.update_idletasks()
        winapi.make_no_activate(self.win)

    def _wheel(self, event):
        if self.visible:
            widget = self.win.winfo_containing(event.x_root, event.y_root)
            if widget is not None and str(widget).startswith(str(self.win)):
                self.text.yview_scroll(int(-event.delta / 120), 'units')

    def _press(self, event):
        self._drag = (event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y())

    def _motion(self, event):
        if self._drag:
            self.win.geometry(f'+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}')

    def show(self, result, anchor, area):
        """anchor：按鈕 (x, y, size)；area：可放置範圍（遊戲畫面）。"""
        self.title.configure(text=result.title)
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        for tag in self.text.tag_names():
            if tag.startswith('fold'):
                self.text.tag_delete(tag)
        self._folds = {}
        for i, line in enumerate(result.lines):
            fold = getattr(line, 'fold', None)
            extra = ()
            if fold and fold[0] == 'head':
                head = f'foldhead{fold[1]}'
                extra = (head,)
                self._folds[fold[1]] = fold[2]
                self.text.tag_configure(f'foldbody{fold[1]}', elide=fold[2])
                self.text.tag_configure(head, underline=False)
                self.text.tag_bind(head, '<Button-1>', lambda e, n=fold[1]: self._toggle(n))
                self.text.tag_bind(head, '<Enter>', lambda e: self.text.configure(cursor='hand2'))
                self.text.tag_bind(head, '<Leave>', lambda e: self.text.configure(cursor='arrow'))
            elif fold and fold[0] == 'body':
                extra = (f'foldbody{fold[1]}',)
            for text, style in line:
                self.text.insert('end', text, (style,) + extra)
            if i < len(result.lines) - 1:
                # 換行也要帶摺疊標籤，摺起來時才不會留下空行
                self.text.insert('end', '\n', extra if fold and fold[0] == 'body' else ())
        self.text.configure(state='disabled')
        self.area = area
        self.anchor = anchor
        self._fit(reposition=True)
        self.text.yview_moveto(0)
        self.visible = True
        self._hidden_by_game = False

    def _toggle(self, number):
        body = f'foldbody{number}'
        collapsed = not self._folds.get(number, False)
        self._folds[number] = collapsed
        self.text.tag_configure(body, elide=collapsed)
        start = self.text.tag_ranges(f'foldhead{number}')
        if start:
            index = self.text.search('▶' if not collapsed else '▼', start[0], start[1])
            if index:
                tags = self.text.tag_names(index)
                self.text.configure(state='normal')
                self.text.delete(index)
                self.text.insert(index, '▶' if collapsed else '▼', tags)
                self.text.configure(state='disabled')
        self._fit(reposition=False)

    def _fit(self, reposition):
        """依內容調整高度（最高為遊戲畫面的 85%）。"""
        left, top, right, bottom = self.area
        max_height = max(int(200 * self.scale), int((bottom - top) * 0.85))
        if reposition:
            self.win.geometry(f'{self.width}x{max_height}+-10000+-10000')
            self.win.deiconify()
        else:
            self.win.geometry(f'{self.width}x{max_height}')
        self.win.update_idletasks()
        try:
            content = self.text.count('1.0', 'end', 'ypixels')[0]
        except Exception:
            content = max_height
        height = min(max_height, content + int(50 * self.scale))
        if reposition:
            bx, by, size = self.anchor
            if bx + size / 2 > (left + right) / 2:
                x = bx - self.width - int(8 * self.scale)
            else:
                x = bx + size + int(8 * self.scale)
            y = min(max(top, by - int(40 * self.scale)), max(top, bottom - height))
            self.win.geometry(f'{self.width}x{height}+{int(x)}+{int(y)}')
        else:
            x, y = self.win.winfo_x(), self.win.winfo_y()
            y = min(y, max(top, bottom - height))
            self.win.geometry(f'{self.width}x{height}+{x}+{y}')
        self.win.attributes('-topmost', True)

    def hide(self):
        self.win.withdraw()
        self.visible = False
        self._hidden_by_game = False

    def follow_game(self, game_visible):
        """遊戲切到背景時暫時隱藏，回到遊戲再顯示。"""
        if not game_visible and self.visible:
            self.win.withdraw()
            self.visible = False
            self._hidden_by_game = True
        elif game_visible and self._hidden_by_game:
            self.win.deiconify()
            self.win.attributes('-topmost', True)
            self.visible = True
            self._hidden_by_game = False


class App:
    def __init__(self):
        self.config = Config()
        self.dir = app_dir()
        self.root = tk.Tk()
        self.root.withdraw()
        self.scale = max(1.0, self.root.winfo_fpixels('1i') / 96)
        self.ocr = Ocr()
        self.data = None
        self.data_status = '正在下載網站資料…'
        self.translations = TranslationStore(self.config.get('translations_url'), self.dir)
        self.translator = Translator(self.config, self.dir / 'translations.json', table=self.translations.table)
        self.cards = CardMatcher(self.config['site_url'], self.dir / 'cards')
        self.pipeline = Pipeline(self.ocr, lambda: self.data, self.cards,
                                 lambda data: Renderer(data, self.translator, self.config), self.config)
        self.results = queue.Queue()
        self.hwnd = None
        self.game_pid = None
        self.rect = None
        self.busy = False
        self._search_countdown = 0
        self._closing = False
        self._pending_frame = None
        self._retry_now = threading.Event()
        self.button = FloatingButton(self, int(48 * self.scale))
        self.popup = Popup(self, self.scale)
        threading.Thread(target=self._load_data, daemon=True).start()
        threading.Thread(target=self._warm_up, daemon=True).start()
        self.root.after(50, self._tick)
        self.root.after(100, self._pump)
        self.root.after(600, self._welcome)

    # ---- 背景工作 ----
    def _load_data(self):
        """下載網站資料；失敗會自動重試（5 秒起，最長每 60 秒一次），成功後定期更新。"""
        delay, attempt = 5, 0
        max_age = float(self.config.get('data_max_age_hours', 12))
        while not self._closing:
            attempt += 1
            if self.data is None and attempt > 1:
                self.data_status = f'正在重新下載網站資料（第 {attempt} 次）…'
            log.info(self.translations.refresh(float(self.config.get('translations_max_age_hours', 6))))
            try:
                data, status = load_data(self.config['data_url'], self.dir, max_age)
                first = self.data is None
                self.data, self.data_status = data, status
                log.info('%s：%d 個旅程事件、%d 張阿爾克那', status, data.journey_count(), len(data.cards))
                if first:
                    self._rerun_pending()
                    threading.Thread(target=self._prefetch_cards, args=(data,), daemon=True).start()
                stale = status.startswith('無法連線')
            except Exception as exc:
                log.warning('網站資料載入失敗（第 %d 次）：%s', attempt, exc)
                self.data_status = f'下載失敗，{delay} 秒後自動重試（已試 {attempt} 次）：{exc}'
                stale = True
            if stale:
                wait = delay
                delay = min(delay * 2, 60)
            else:
                wait, delay, attempt = max_age * 3600, 5, 0
            self._retry_now.wait(wait)
            self._retry_now.clear()

    def _prefetch_cards(self, data):
        """先在背景下載所有卡圖並算好特徵，第一次遇到阿爾克那事件時就不用等下載。"""
        from concurrent.futures import ThreadPoolExecutor

        def one(card):
            try:
                self.cards.reference(card)
                return True
            except Exception as exc:
                log.warning('預先下載卡圖 %s 失敗：%s', card.get('id'), exc)
                return False

        with ThreadPoolExecutor(max_workers=4) as pool:
            done = sum(pool.map(one, data.cards))
        log.info('卡圖預先下載完成：%d / %d', done, len(data.cards))

    def _rerun_pending(self):
        frame, self._pending_frame = self._pending_frame, None
        if frame is not None:
            log.info('網站資料就緒，自動重新辨識上一次的畫面')
            threading.Thread(target=self._work, args=(frame,), daemon=True).start()

    def _warm_up(self):
        try:
            self.ocr.warm_up()
        except Exception:
            log.exception('OCR 初始化失敗')

    def _welcome(self):
        lines = [[('左鍵點「旅」按鈕：辨識目前的旅程事件／阿爾克那事件', 'effect')],
                 [('拖曳按鈕：移動位置', 'effect')],
                 [('右鍵點按鈕：結束程式', 'effect')]]
        if not self.hwnd:
            lines.insert(0, [('尚未找到 StarSavior 遊戲視窗，開啟遊戲後按鈕會自動移到遊戲畫面上。', 'warn')])
        self._show(Result('旅程助手已啟動', lines))
        self.root.after(6000, lambda: self.popup.hide() if self.popup.title.cget('text') == '旅程助手已啟動' else None)

    # ---- 追蹤遊戲視窗 ----
    def _tick(self):
        try:
            self._track_game()
        except Exception:
            log.exception('追蹤遊戲視窗失敗')
        self.root.after(250, self._tick)

    def _track_game(self):
        if self.hwnd and not winapi.is_window(self.hwnd):
            self.hwnd = self.game_pid = None
        if not self.hwnd:
            self._search_countdown -= 1
            if self._search_countdown <= 0:
                self._search_countdown = 8  # 約每 2 秒找一次
                self.hwnd = winapi.find_game_window(self.config['process_names'], self.config['process_keyword'])
                self.game_pid = winapi.window_pid(self.hwnd) if self.hwnd else None
                if self.hwnd:
                    log.info('找到遊戲視窗 %s（PID %s）', self.hwnd, self.game_pid)
        if not self.hwnd:
            self.rect = None
            self.button.set_state('busy' if self.busy else 'waiting')
            self.button.show(True)
            if not self._dragging():
                sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
                self.button.move(sw - self.button.size - 24 * self.scale, sh * 0.6)
            return
        if not self.busy:
            self.button.set_state('ready')
        rect = winapi.client_rect(self.hwnd)
        foreground = winapi.foreground_pid()
        visible = (rect is not None and not winapi.is_minimized(self.hwnd)
                   and foreground in (self.game_pid, os.getpid()))
        if self.busy:
            return  # 截圖時按鈕暫時隱藏，不要在這裡顯示回來
        self.button.show(visible)
        self.popup.follow_game(visible)
        if not visible:
            return
        self.rect = rect
        if not self._dragging():
            fx, fy = self.config.get('button_position', [0.965, 0.42])
            left, top, right, bottom = rect
            size = self.button.size
            x = min(max(left, left + fx * (right - left) - size / 2), right - size)
            y = min(max(top, top + fy * (bottom - top) - size / 2), bottom - size)
            self.button.move(x, y)

    def _dragging(self):
        return self.button._drag is not None

    def button_dragged(self):
        if not self.rect:
            return
        left, top, right, bottom = self.rect
        x, y = self.button.position()
        size = self.button.size
        fx = (x + size / 2 - left) / max(1, right - left)
        fy = (y + size / 2 - top) / max(1, bottom - top)
        self.config['button_position'] = [round(min(max(fx, 0), 1), 4), round(min(max(fy, 0), 1), 4)]
        self.config.save()

    # ---- 辨識 ----
    def scan(self):
        if self.busy:
            return
        if not self.hwnd or not self.rect:
            self._show(Result('找不到遊戲', [[('找不到 StarSavior 的遊戲視窗，請先開啟遊戲。', 'warn')],
                                         [('右鍵點按鈕可結束程式。', 'dim')]]))
            return
        self.busy = True
        self.button.set_state('busy')
        self.popup.hide()
        self.button.show(False)  # 避免按鈕或小窗被截進畫面
        self.root.update_idletasks()
        self.root.after(120, self._capture)

    def _capture(self):
        try:
            frame = winapi.grab(winapi.client_rect(self.hwnd) or self.rect)
        except Exception as exc:
            log.exception('截圖失敗')
            self.results.put(Result('截圖失敗', [[(str(exc), 'warn')]]))
            return
        finally:
            self.button.show(True)
        if self.config.get('save_last_capture'):
            try:
                frame.save(self.dir / 'last_capture.png')
            except OSError:
                pass
        threading.Thread(target=self._work, args=(frame,), daemon=True).start()

    def _work(self, frame):
        started = time.perf_counter()
        try:
            result = self.pipeline.run(frame)
        except Exception as exc:
            log.exception('辨識失敗')
            result = Result('發生錯誤', [[(f'{type(exc).__name__}: {exc}', 'warn')]])
        elapsed = time.perf_counter() - started
        log.info('辨識完成：%s，耗時 %.2f 秒', result.title, elapsed)
        result.lines.append([(f'耗時 {elapsed:.1f} 秒', 'dim')])
        if result.title == '資料尚未就緒':
            # 資料還沒好：記住這張截圖，下載成功後自動重新辨識，並立刻再試一次下載
            self._pending_frame = frame
            self._retry_now.set()
            result.lines.append([('狀態：' + self.data_status, 'dim')])
            result.lines.append([('資料下載完成後會自動重新辨識這個畫面，不需要再點。', 'note')])
            self.results.put(result)
            if self.data is not None:  # 剛好在這段期間下載完成
                self._rerun_pending()
            return
        self.results.put(result)

    def _pump(self):
        try:
            while True:
                result = self.results.get_nowait()
                self.busy = False
                self.button.set_state('ready' if self.hwnd else 'waiting')
                self._show(result)
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _show(self, result):
        x, y = self.button.position()
        area = self.rect or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.popup.show(result, (x, y, self.button.size), area)

    def quit(self):
        log.info('結束程式')
        self._closing = True
        self._retry_now.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
