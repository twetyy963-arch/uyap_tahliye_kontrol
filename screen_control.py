# -*- coding: utf-8 -*-
"""
UYAP Tahliye Kontrol Robotu - Ekran ve Giriş Kontrol Modülü (Win32 API)
"""
import time
import ctypes
from ctypes import wintypes
from PIL import Image, ImageGrab

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 Tuş Kodları
VK_RETURN  = 0x0D
VK_SPACE   = 0x20
VK_ESCAPE  = 0x1B
VK_CONTROL = 0x11
VK_A       = 0x41
VK_C       = 0x43
VK_V       = 0x56

CF_UNICODETEXT = 13
GMEM_MOVEABLE  = 0x0002

def _set_clipboard_text(text):
    """Win32 API ile panoya metin yazar (harici kütüphane gerektirmez)."""
    try:
        if not user32.OpenClipboard(0):
            return False
        try:
            user32.EmptyClipboard()
            raw_bytes = (str(text) + "\0").encode("utf-16le")
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_bytes))
            if not h_mem:
                return False
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return False
            ctypes.memmove(p_mem, raw_bytes, len(raw_bytes))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            user32.CloseClipboard()
    except Exception:
        return False

def _get_clipboard_text():
    """Win32 API ile panodan metin okur (harici kütüphane gerektirmez)."""
    try:
        if not user32.OpenClipboard(0):
            return ""
        try:
            h_mem = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_mem:
                return ""
            kernel32.GlobalLock.restype = ctypes.c_void_p
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return ""
            val = ctypes.c_wchar_p(p_mem).value
            kernel32.GlobalUnlock(h_mem)
            return val or ""
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""

class ScreenController:
    def __init__(self, confidence=0.70):
        self.confidence = confidence

    def prevent_sleep(self, enable=True):
        """Windows'un ekranı kapatmasını veya uyku moduna geçmesini engeller."""
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        try:
            if enable:
                kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            else:
                kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass

    def check_emergency_stop(self):
        """Kullanıcı ESC tuşuna bastıysa veya fareyi sol üst köşeye çektiyse anında True döner."""
        if bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000):
            return True
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if pt.x <= 15 and pt.y <= 15:
            return True
        return False

    def bring_window_to_front(self, window_title="uyap"):
        """
        Başlığında UYAP geçen pencereyi öne getirir.
        Geliştirme ortamlarını (Antigravity, VS Code, Python vb.) KESİNLİKLE öne getirmez.
        """
        EXCLUDED = [
            "antigravity", "visual studio", "code", "python", "scratch",
            ".py", ".json", ".bat", ".ps1", "powershell", "cmd", "terminal",
            "tahliye_kontrol", "tahliye robotu", "uyap tahliye"
        ]

        def enum_windows_proc(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()

                    # Antigravity veya editör penceresiyse KESİNLİKLE ATLAMA YAP
                    if any(ex in title for ex in EXCLUDED):
                        return True

                    # Gerçek UYAP / Adalet / Java penceresi mi?
                    uyap_signals = [
                        "uyap bilişim", "uyap bilisim", "adalet bakanlığı",
                        "adalet bakanligi", "kln_ceza", "evrak hazırlama",
                        "evrak hazirlama", "kalan cezasını", "kalan cezasini"
                    ]
                    is_uyap = any(sig in title for sig in uyap_signals) or (
                        window_title.lower() in title and not any(ex in title for ex in EXCLUDED)
                    )

                    if is_uyap:
                        if user32.IsIconic(hwnd):
                            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        else:
                            user32.ShowWindow(hwnd, 5)  # SW_SHOW
                        user32.SetForegroundWindow(hwnd)
                        time.sleep(0.08)
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        try:
            user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
        except Exception:
            pass

    def grab_screen(self, bbox=None):
        """Ekran görüntüsü alır."""
        try:
            return ImageGrab.grab(bbox=bbox)
        except Exception:
            try:
                time.sleep(0.1)
                return ImageGrab.grab(bbox=bbox)
            except Exception:
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                return Image.new("RGB", (w, h), color=(240, 240, 240))

    def move_to(self, x, y):
        user32.SetCursorPos(int(x), int(y))

    def click(self, x, y, delay=0.08):
        if self.check_emergency_stop():
            return
        self.move_to(x, y)
        time.sleep(0.04)
        if self.check_emergency_stop():
            return
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
        time.sleep(delay)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
        time.sleep(0.04)

    def double_click(self, x, y):
        if self.check_emergency_stop():
            return
        self.click(x, y, delay=0.06)
        time.sleep(0.08)
        self.click(x, y, delay=0.06)

    def press_key(self, vk_code, delay=0.05):
        if self.check_emergency_stop():
            return
        scan = user32.MapVirtualKeyW(vk_code, 0)
        user32.keybd_event(vk_code, scan, 0, 0)
        time.sleep(delay)
        user32.keybd_event(vk_code, scan, 2, 0)  # KEYEVENTF_KEYUP
        time.sleep(0.02)

    def press_esc(self):
        self.press_key(VK_ESCAPE)

    def press_enter(self):
        self.press_key(VK_RETURN)

    def press_space(self):
        self.press_key(VK_SPACE)

    def clear_text_field(self):
        """Kutudaki metni Ctrl+A ve Backspace ile siler."""
        if self.check_emergency_stop():
            return
        scan_ctrl = user32.MapVirtualKeyW(VK_CONTROL, 0)
        scan_a    = user32.MapVirtualKeyW(VK_A, 0)
        scan_bs   = user32.MapVirtualKeyW(0x08, 0)

        user32.keybd_event(VK_CONTROL, scan_ctrl, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_A, scan_a, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_A, scan_a, 2, 0)
        user32.keybd_event(VK_CONTROL, scan_ctrl, 2, 0)
        time.sleep(0.02)
        user32.keybd_event(0x08, scan_bs, 0, 0)  # Backspace
        time.sleep(0.02)
        user32.keybd_event(0x08, scan_bs, 2, 0)

    def type_text(self, text, char_delay=0.005):
        """Panodan kopyala-yapıştır veya klavye simülasyonu ile metni kutuya yazar."""
        if self.check_emergency_stop():
            return
        copied = _set_clipboard_text(str(text))
        if copied:
            time.sleep(0.02)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_V, 0, 2, 0)
            user32.keybd_event(VK_CONTROL, 0, 2, 0)
        else:
            # Doğrudan Unicode klavye yazımı
            for char in str(text):
                code = ord(char)
                user32.keybd_event(0, code, 4, 0)  # KEYEVENTF_UNICODE
                time.sleep(char_delay)
                user32.keybd_event(0, code, 6, 0)

    def clear_and_type(self, x, y, text):
        self.click(x, y)
        time.sleep(0.04)
        self.clear_text_field()
        time.sleep(0.04)
        self.type_text(text)

    def copy_selection(self, x, y):
        """Alana tıklar ve sadece Ctrl+C yaparak seçili metni döndürür (tüm ekranı seçip bozmaz)."""
        _set_clipboard_text("")
        self.click(x, y)
        time.sleep(0.04)

        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_C, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        time.sleep(0.06)

        return _get_clipboard_text().strip()

    def select_all_and_copy(self, x, y):
        """Alana tıklar, Ctrl+A ve Ctrl+C yaparak panodaki metni döndürür."""
        _set_clipboard_text("")

        self.click(x, y)
        time.sleep(0.04)

        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_A, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_A, 0, 2, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_C, 0, 2, 0)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        time.sleep(0.08)

        return _get_clipboard_text().strip()
