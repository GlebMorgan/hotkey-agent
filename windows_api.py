import ctypes

from ctypes import wintypes


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


class Input(ctypes.Structure):
    class InputUnion(ctypes.Union):
        _fields_ = [('mi', MouseInput), ('ki', KeyboardInput), ('hi', HardwareInput)]

    _anonymous_ = ['u']
    _fields_ = [('type', wintypes.DWORD), ('u', InputUnion)]
