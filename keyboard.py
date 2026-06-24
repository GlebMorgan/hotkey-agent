import ctypes

import win32con

from windows_api import Input, KeyboardInput, Windows


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


class KeyCombination:
    key: int
    modifiers: tuple[int]

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
            mask |= MODIFIERS.get(mod, 0)
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
            elif key in MODIFIER_KEYS:
                modifiers.append(MODIFIER_KEYS[key])
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
        return Input(type=win32con.INPUT_KEYBOARD, ki=KeyboardInput(wVk=vk, dwFlags=flags))

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
