"""Windows API：找遊戲程序與視窗、取得畫面範圍、截圖、懸浮窗不搶焦點。"""
import ctypes
import os
from ctypes import wintypes

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.GetParent.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND
    kernel32.CreateMutexW.restype = wintypes.HANDLE

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
ERROR_ALREADY_EXISTS = 183


def set_dpi_aware():
    """讓座標使用實際像素，截圖和視窗位置才會對齊。"""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_mutex = None


def single_instance(name='Local\\StarSaviorJourneyHelper'):
    """已經有一個在執行時回傳 False。"""
    global _mutex
    if not IS_WINDOWS:
        return True
    _mutex = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def find_game_pids(names, keyword):
    import psutil
    wanted = {n.lower() for n in names}
    keyword = (keyword or '').lower()
    pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        name = (proc.info.get('name') or '').lower()
        compact = name.replace(' ', '').replace('_', '').replace('-', '')
        if name in wanted or (keyword and keyword in compact):
            pids.append(proc.info['pid'])
    return pids


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def client_rect(hwnd):
    """回傳遊戲畫面（不含標題列與邊框）的螢幕座標 (left, top, right, bottom)。"""
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom


def find_game_window(names, keyword):
    """找出遊戲程序面積最大的可見主視窗；找不到回傳 None。"""
    if not IS_WINDOWS:
        return None
    pids = set(find_game_pids(names, keyword))
    if not pids:
        return None
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd) and window_pid(hwnd) in pids and not user32.GetParent(hwnd):
            rect = client_rect(hwnd)
            if rect and rect[2] - rect[0] > 200 and rect[3] - rect[1] > 150:
                found.append(((rect[2] - rect[0]) * (rect[3] - rect[1]), hwnd))
        return True

    user32.EnumWindows(callback, 0)
    return max(found)[1] if found else None


def is_window(hwnd):
    return bool(hwnd) and IS_WINDOWS and bool(user32.IsWindow(hwnd))


def is_minimized(hwnd):
    return IS_WINDOWS and bool(user32.IsIconic(hwnd))


def foreground_pid():
    if not IS_WINDOWS:
        return None
    hwnd = user32.GetForegroundWindow()
    return window_pid(hwnd) if hwnd else None


def toplevel_hwnd(tk_window):
    return user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()


def make_no_activate(tk_window):
    """點懸浮窗時不搶走遊戲的焦點，也不顯示在工作列。"""
    if not IS_WINDOWS:
        return
    hwnd = toplevel_hwnd(tk_window)
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)


def grab(rect):
    from PIL import ImageGrab
    return ImageGrab.grab(bbox=rect, all_screens=True).convert('RGB')
