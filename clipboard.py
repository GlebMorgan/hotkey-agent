from enum import Enum
from typing import Iterator, Self, TypeAlias

import win32clipboard as win32cb
import win32con


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
