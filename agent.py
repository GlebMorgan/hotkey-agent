"""
Background agent to execute actions on registered hotkey invocations
Must run in background when hotkeys are invoked
First working PoC: inserts a formatted GitLab MR link on Ctrl+Alt+V
"""

import ctypes
import re

from ctypes import wintypes
from enum import Enum
from typing import Callable, Iterator, Self, TypeAlias

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
    PostThreadMessageW = ctypes.windll.user32.PostThreadMessageW
    GetCurrentThreadId = ctypes.windll.kernel32.GetCurrentThreadId


class KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]

    def __init__(self, key: int, flags: int = 0):
        super().__init__(key, 0, flags, 0, 0)


class MouseInput(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', wintypes.WPARAM),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ('uMsg', wintypes.DWORD),
        ('wParamL', wintypes.WORD),
        ('wParamH', wintypes.WORD),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [('mi', MouseInput), ('ki', KeyboardInput), ('hi', HardwareInput)]


class Input(ctypes.Structure):
    _anonymous_ = ['u']
    _fields_ = [('type', wintypes.DWORD), ('u', InputUnion)]

    @classmethod
    def key_press(cls, key: int) -> Self:
        self = cls(type=win32con.INPUT_KEYBOARD)
        self.u.ki = KeyboardInput(key)
        return self

    @classmethod
    def key_release(cls, key: int) -> Self:
        self = cls(type=win32con.INPUT_KEYBOARD)
        self.u.ki = KeyboardInput(key, win32con.KEYEVENTF_KEYUP)
        return self


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
    key: int
    modifiers: tuple[int]

    MODIFIER_KEYS = {
        "ctrl": win32con.VK_CONTROL,
        "shift": win32con.VK_SHIFT,
        "alt": win32con.VK_MENU,
        "win": win32con.VK_LWIN,
    }

    MODIFIERS = {
        win32con.VK_CONTROL: win32con.MOD_CONTROL,
        win32con.VK_SHIFT: win32con.MOD_SHIFT,
        win32con.VK_MENU: win32con.MOD_ALT,
        win32con.VK_LWIN: win32con.MOD_WIN,
    }

    def __init__(self, combination: str):
        self.key, self.modifiers = self.decode(combination)

    def __hash__(self) -> int:
        return hash(self.keys)

    @property
    def keys(self) -> tuple[int, ...]:
        return self.modifiers + (self.key,)

    @property
    def modifiers_mask(self) -> int:
        mask = 0
        for mod in self.modifiers:
            mask |= self.MODIFIERS.get(mod, 0)
        return mask

    @classmethod
    def decode(cls, combination: str) -> tuple[int, tuple[int]]:
        keys = [key.strip().lower() for key in combination.split("+")]
        modifiers = []
        main_key = None

        for key in keys:
            if len(key) == 1:
                if not key or not key.isascii():
                    raise ValueError(f"Invalid key: '{key}'")
                if main_key is not None:
                    raise ValueError(f"Multiple non-modifier keys: '{main_key}', '{key.upper()}'")
                main_key = key.upper()
            elif key in cls.MODIFIER_KEYS:
                modifiers.append(cls.MODIFIER_KEYS[key])
            else:
                raise ValueError(f"Unknown modifier: '{key}'")

        if main_key is None:
            raise ValueError("No key specified in combination")

        return ord(main_key), tuple(modifiers)


class KeySequence:
    def __init__(self, combination_string: str):
        self.combination = KeyCombination(combination_string)

    @staticmethod
    def keyboard_event(vk: int, flags: int = 0) -> Input:
        return Input(type=win32con.INPUT_KEYBOARD, ki=KeyboardInput(vk, flags))

    @classmethod
    def keyboard_event_sequence(cls, keycodes: tuple[int, ...]) -> ctypes.Array:
        n = len(keycodes) * 2
        inputs = (Input * n)()
        for i, vk in enumerate(keycodes):
            inputs[i] = cls.keyboard_event(vk)
        for i, vk in enumerate(reversed(keycodes), len(keycodes)):
            inputs[i] = cls.keyboard_event(vk, win32con.KEYEVENTF_KEYUP)
        return inputs

    def apply(self):
        sequence = self.keyboard_event_sequence(self.combination.keys)
        n = len(sequence)
        sent = Windows.SendInput(n, ctypes.byref(sequence), ctypes.sizeof(Input))
        if sent != n:
            error = ctypes.GetLastError()
            raise OSError(f"SendInput failed: sent {sent}/{n}. Error: {ctypes.FormatError(error)}")


def transform_clipboard():
    with Clipboard() as clipboard:
        url = clipboard.get(Clipboard.Format.UNICODE)
        if url is None or not isinstance(url, str):
            raise ValueError("Clipboard does not contain a URL")

        print("Url:", url)

        hyperlink = generate_mr_hyperlink(url)
        print("Hyperlink:", hyperlink)

        clipboard.set(Clipboard.Format.HTML, hyperlink)
        clipboard.reload()

        html = clipboard.get(Clipboard.Format.HTML)
        print("HTML:", html)


class HotkeyAgent:
    actions: list[Callable] = []

    def __enter__(self):
        self.register_console_control_handler()
        return self

    def __exit__(self, exc_type, exc, tb):
        for hotkey_id, action in enumerate(self.actions):
            Windows.UnregisterHotKey(None, hotkey_id)

    @staticmethod
    def register_console_control_handler():
        """Required to handle Ctrl+C event and terminate the script
        while it is blocked by Windows.GetMessageW() call"""
        thread_id = Windows.GetCurrentThreadId()

        def exit_handler(ctrl_type):
            Windows.PostThreadMessageW(thread_id, win32con.WM_QUIT, 0, 0)
            return True

        win32api.SetConsoleCtrlHandler(exit_handler, True)

    def register_action(self, combination: str, callback: Callable):
        hotkey = KeyCombination(combination)
        new_hotkey_id = len(self.actions)

        result = Windows.RegisterHotKey(None, new_hotkey_id, hotkey.modifiers_mask, hotkey.key)
        if not result:
            error = ctypes.GetLastError()
            print(f"Failed to register hotkey: {ctypes.FormatError(error)}")
            return

        self.actions.append(callback)

    def run(self):
        event = wintypes.MSG()
        while Windows.GetMessageW(ctypes.byref(event), None, 0, 0) != 0:
            event_id = event.wParam
            if event.message == win32con.WM_HOTKEY and event_id < len(self.actions):
                print(f"Event {event_id} triggered")
                self.execute_action(self.actions[event_id])
            Windows.TranslateMessage(ctypes.byref(event))
            Windows.DispatchMessageW(ctypes.byref(event))

    @staticmethod
    def execute_action(action: Callable):
        try:
            action()
        except Exception as e:
            print(f"Error: {e}")
            win32api.MessageBeep(win32con.MB_ICONHAND)


def paste_gitlab_mr_link():
    transform_clipboard()
    KeySequence("Ctrl+V").apply()


if __name__ == "__main__":
    with HotkeyAgent() as agent:
        agent.register_action("Ctrl+Alt+V", paste_gitlab_mr_link)
        agent.run()
