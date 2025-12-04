"""
Background agent to execute actions on registered hotkey invocations
Must run in background when hotkeys are invoked
First working PoC: inserts a formatted GitLab MR link on Ctrl+Alt+V
"""

import ctypes
import re

from ctypes import wintypes
from enum import Enum
from typing import Iterator, Self, TypeAlias

import win32api
import win32clipboard as win32cb
import win32con


class Windows:
    RegisterHotKey = ctypes.windll.user32.RegisterHotKey
    UnregisterHotKey = ctypes.windll.user32.UnregisterHotKey
    GetMessageW = ctypes.windll.user32.GetMessageW
    TranslateMessage = ctypes.windll.user32.TranslateMessage
    DispatchMessageW = ctypes.windll.user32.DispatchMessageW
    KeyboardEvent = ctypes.windll.user32.keybd_event
    SendInput = ctypes.windll.user32.SendInput


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', wintypes.WPARAM),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg', wintypes.DWORD),
        ('wParamL', wintypes.WORD),
        ('wParamH', wintypes.WORD),
    ]


class UNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ['u']
    _fields_ = [('type', wintypes.DWORD), ('u', UNION)]


def make_input(vk, flags=0):
    ki = KEYBDINPUT()
    ki.wVk = vk
    ki.wScan = 0
    ki.dwFlags = flags
    ki.time = 0
    ki.dwExtraInfo = 0
    inp = INPUT()
    inp.type = 1  # INPUT_KEYBOARD
    inp.u.ki = ki
    return inp


def send_ctrl_v():
    VK_CONTROL = 0x11
    VK_V = ord('V')
    KEYEVENTF_KEYUP = 0x0002

    inputs = (INPUT * 4)()
    inputs[0] = make_input(VK_CONTROL, 0)  # ctrl down
    inputs[1] = make_input(VK_V, 0)  # v down
    inputs[2] = make_input(VK_V, KEYEVENTF_KEYUP)  # v up
    inputs[3] = make_input(VK_CONTROL, KEYEVENTF_KEYUP)  # ctrl up

    n = Windows.SendInput(4, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if n != 4:
        error = ctypes.GetLastError()
        raise OSError(f"SendInput failed: returned {n}, GetLastError={error}")
    return n


PROJECTS = {
    "fleet/tms/teltonika-tdf": "TDF",
    "fleet/tms/apps/telematics-app": "TAPP",
    "fleet/tms/apps/daughterboard-application": "DAPP",
    "fleet/tms/apps/extension-application": "EXTAPP",
    "fleet/tms/apps/ble-extension-application": "BLEAPP",
    "fleet/tms/apps/can-extension-application": "CANAPP",
    "fleet/tms/apps/teltonika-bootloader": "TBL",
    "fleet/tms/tools/tms-python-console": "TMS-Console",
    "fleet/tms/libraries/protobuf-communication": "Proto",
    "fleet/tms/libraries/extapp-protobuf-communication": "ExtMCU-Proto",
    "fleet/tms/libraries/extmcu-protobuf-communication": "ExtMCU-Proto",
    "fleet/tms/tools/gitlab-roulette": "GitLab-Roulette",
    "fleet/fmb/fmb-firmware": "FMB",
    "fleet/fmb6/fmb6-firmware": "FMB6",
    "fleet/fmb/tetra-protocol": "TETRA",
    "dotnet/confi/tct": "TCT",
    "fleet/tms/tools/tct-configurations": "TCT-Cfg",
    "fleet/tms/tools/tct-localization": "TCT-Loc",
    "fleet/fmb/fmb-configurator": "FMB-Configurator",
    "fleet/fmb/cfg-configurations": "FMB-Cfg",
    "fleet/fmb/cfg-localization": "FMB-Loc",
}


def get_project_alias(project_path: str) -> str:
    for prefix, alias in PROJECTS.items():
        if project_path.startswith(prefix):
            return alias
    return project_path.split("/")[-1]


def generate_mr_hyperlink(url: str) -> str:
    """https://gps-gitlab.teltonika.lt/fleet/tms/teltonika-tdf/-/merge_requests/0"""

    GITLAB_MR_PATTERN = re.compile(  # pylint: disable=invalid-name
        r"https://gps-gitlab.teltonika.lt/(?P<path>.+?)/-/merge_requests/(?P<id>\d+)"
    )

    match = GITLAB_MR_PATTERN.match(url)
    if not match:
        raise ValueError("Not a valid GitLab merge request URL: " + url)

    alias = get_project_alias(match.group("path"))
    mr_id = match.group("id")
    return f'<a href="{url}">{alias}/{mr_id}</a>'


class Clipboard:
    Data: TypeAlias = str | bytes

    class Format(Enum):
        TEXT = win32con.CF_TEXT
        UNICODE = win32con.CF_UNICODETEXT
        HTML = win32cb.RegisterClipboardFormat("HTML Format")

    data: dict[int, Data | None]

    def __enter__(self) -> Self:
        win32cb.OpenClipboard()
        self.load()
        return self

    def __exit__(self, *_):
        win32cb.CloseClipboard()

    def load(self):
        self.data = dict(self._iter_formats_())

    def get(self, cb_format: Format) -> Data | None:
        return self.data.get(cb_format.value)

    def set(self, cb_format: Format, value: str):
        if cb_format == Clipboard.Format.HTML:
            data = self.to_html_format(value).encode("utf-8")
        else:
            data = value
        self.data[cb_format.value] = data

    def reload(self):
        win32cb.EmptyClipboard()
        for format_id, data in self.data.items():
            if data is None:
                continue
            try:
                win32cb.SetClipboardData(format_id, data)
            except TypeError:
                continue

    @staticmethod
    def _iter_formats_() -> Iterator[tuple[int, Data | None]]:
        format_id = 0
        while format_id := win32cb.EnumClipboardFormats(format_id):
            try:
                data = win32cb.GetClipboardData(format_id)
            except TypeError:
                data = None
            yield (format_id, data)

    @staticmethod
    def to_html_format(html: str) -> str:
        """https://learn.microsoft.com/en-us/windows/win32/dataxchg/html-clipboard-format"""

        header = (
            "Version:1.0\r\n"
            "StartHTML:{000000}\r\n"
            "EndHTML:{000001}\r\n"
            "StartFragment:{000002}\r\n"
            "EndFragment:{000003}\r\n"
        )
        fragment_prefix = "<html><body><!--StartFragment-->"
        fragment_postfix = "<!--EndFragment--></body></html>"

        html_start = len(header)
        fragment_start = html_start + len(fragment_prefix)
        fragment_end = fragment_start + len(html)
        html_end = fragment_end + len(fragment_postfix)

        header = header.format(
            f"{html_start:08d}",
            f"{html_end:08d}",
            f"{fragment_start:08d}",
            f"{fragment_end:08d}",
        )

        return header + fragment_prefix + html + fragment_postfix


class KeyCombination:
    KEY_MAP = {
        "ctrl": win32con.VK_CONTROL,
        "shift": win32con.VK_SHIFT,
        "alt": win32con.VK_MENU,
        "win": win32con.VK_LWIN,
    }

    def __init__(self, combination: str) -> None:
        self.keys = self.decode_combination(combination)

    @classmethod
    def decode_combination(cls, combination: str) -> list[int]:
        parts = [item.strip() for item in combination.lower().split("+")]
        keys = []
        for part in parts:
            if part in cls.KEY_MAP:
                keys.append(cls.KEY_MAP[part])
            elif len(part) == 1:
                keys.append(ord(part.upper()))
            else:
                raise ValueError(f"Unknown key: {part}")
        return keys

    def apply(self):
        for key in self.keys:
            Windows.KeyboardEvent(key, 0, 0, 0)
        for key in reversed(self.keys):
            Windows.KeyboardEvent(key, 0, win32con.KEYEVENTF_KEYUP, 0)


def transform_clipboard():
    with Clipboard() as clipboard:
        url = clipboard.get(Clipboard.Format.UNICODE)
        if str is None or not isinstance(url, str):
            raise ValueError("Clipboard does not contain a URL")

        print("Url:", url)

        hyperlink = generate_mr_hyperlink(url)
        print("Hyperlink:", hyperlink)

        clipboard.set(Clipboard.Format.HTML, hyperlink)
        clipboard.reload()

        html = clipboard.get(Clipboard.Format.HTML)
        print("HTML:", html)


def main():
    try:
        transform_clipboard()
        # KeyCombination("Ctrl+V").apply()
        send_ctrl_v()
    except Exception as e:
        print(f"Error: {e}")
        win32api.MessageBeep(win32con.MB_ICONHAND)


def message_loop():
    WM_HOTKEY = 0x0312
    HOTKEY_ID = 1

    if not Windows.RegisterHotKey(None, HOTKEY_ID, win32con.MOD_CONTROL | win32con.MOD_ALT, ord('V')):
        raise RuntimeError("RegisterHotKey failed")
    try:
        msg = wintypes.MSG()
        while Windows.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                print("Ctrl+Alt+V pressed")
                main()
            Windows.TranslateMessage(ctypes.byref(msg))
            Windows.DispatchMessageW(ctypes.byref(msg))
    finally:
        Windows.UnregisterHotKey(None, HOTKEY_ID)


if __name__ == "__main__":
    message_loop()
