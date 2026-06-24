import ctypes

from ctypes import wintypes
from typing import Callable

import win32api
import win32con

from keyboard import KeyCombination
from windows_api import Windows


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
