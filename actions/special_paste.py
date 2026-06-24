import re

from clipboard import Clipboard
from keyboard import KeySequence


PROJECTS = {
    # T5 Projects
    "fleet/tms/teltonika-tdf": "TDF",
    "fleet/tms/apps/telematics-app": "TAPP",
    "fleet/tms/apps/can-extension-application": "CANAPP",
    "fleet/tms/apps/ble-extension-application": "BLEAPP",
    "fleet/tms/apps/extension-application": "EXTAPP",
    "fleet/tms/apps/daughterboard-application": "DAPP",
    "fleet/tms/apps/btsx-application": "BTSX",
    "fleet/tms/apps/teltonika-bootloader": "TBL",
    "fleet/tms/libraries/protobuf-communication": "Proto",
    "fleet/tms/libraries/extapp-protobuf-communication": "ExtMCU-Proto",
    "fleet/tms/libraries/extmcu-protobuf-communication": "ExtMCU-Proto",
    "fleet/tms/platforms/stm32/stm32g0xx_hal_driver": "STM32-HAL",

    # T5 Tools
    "fleet/tms/tools/ci-cd-cfg": "CI-CD",
    "fleet/tms/tools/tms-python-console": "TMS-Console",
    "fleet/tms/tools/gitlab-roulette": "GitLab-Roulette",
    "jan.smolskij/t5-can-functionality-testing": "CAN-Testing",
    "fleet/tms/tools/ag3335-airoha-logging-tool-src": "AG-Logger",

    # TCT
    "dotnet/confi/tct": "TCT",
    "fleet/tms/tools/tct-configurations": "TCT-Cfg",
    "fleet/tms/tools/tct-localization": "TCT-Loc",

    # Factory
    "fleet/tms/tools/daughterboard-application-testing": "Nightly",
    "fleet/tms/libraries/factory-testing-configurations": "Factory",
    "dotnet/factory/tt-evalon/evalon-testing-configurations": "Evalon-Cfg",

    # Protocols
    "fleet/fmb/tetra-protocol": "TETRA",
    "dotnet/fota/fota-protocols": "FOTA",

    # FMB6
    "fleet/fmb6/fmb6-firmware": "FMB6",
    "fleet/fmb6/fmb6-bootloader": "FMB6-Bootloader",
    "fleet/fmb6/fmb6-common_ids": "FMB6-IDs",
    "fleet/fmb6/fmb6-specprojects": "FMB6-Spec",
    "fleet/fmb6/fmb6-documentation": "FMB6-Docs",
    "fleet/fmb6/fmb6-tools": "FMB6-Tools",
    "fleet/fmb6/tiny-usb-lib": "TinyUSB",
    "fleet/fmb6/fmb6-ble_sdk": "BLE-SDK",
    "fleet/drivers/FLASH_LIB_FM6": "FLASH-LIB",
    "fleet/drivers/axl_hal_fm6": "AXL",
    "fleet/tools/tcp_udp_server": "ServerMain",

    # Configurator
    "fleet/fmb/fmb-configurator": "CONF",
    "fleet/fmb/cfg-configurations": "CFG",
    "fleet/fmb/cfg-localization": "LOC",
    "fleet/fmb/fmb-configurator-branding": "Branding",

    # FMB
    "fleet/fmb/fmb-firmware": "FMB",
    "fleet/fmb/fmb-fmb6-eq-avl-ids": "FMB-AVLIDs",
    "fleet/fmb/fmb-testtool": "TestTool",
    "fleet/fmb/fmb-docs-teltonika-lt": "FMB-Docs",

    # Other
    "gleb.klukach/gk-c-training-workshop-task": "CPP-Workshop",
    "fleet/tools/rnd_script": "RND-Autofill",
}


def get_gitlab_project_alias(project_path: str) -> str:
    for prefix, alias in PROJECTS.items():
        if project_path.startswith(prefix):
            return alias
    return project_path.split("/")[-1]


def gitlab_mr_link(match: re.Match) -> str:
    """https://gps-gitlab.teltonika.lt/fleet/tms/teltonika-tdf/-/merge_requests/0"""
    alias = get_gitlab_project_alias(match.group("path"))
    mr_id = match.group("id")
    return f'<a href="{match.group(0)}">{alias}/{mr_id}</a>'


def jira_link(match: re.Match) -> str:
    """https://teltonika-telematics.atlassian.net/browse/PRJ-000"""
    return f'<a href="{match.group(0)}">{match.group("key")}</a>'


INPUT_TYPES = {
    r"https://gps-gitlab.teltonika.lt/(?P<path>.+?)/-/merge_requests/(?P<id>\d+)": gitlab_mr_link,
    r"https://teltonika-telematics.atlassian.net/browse/(?P<key>[A-Z0-9]+-\d+)": jira_link,
}


def transform(text: str):
    for pattern, handler in INPUT_TYPES.items():
        match = re.match(pattern, text)
        if match:
            return handler(match)
    raise ValueError(f"Unsupported input '{repr(text)[:92]}'")


def special_paste():
    with Clipboard() as clipboard:
        raw_text = clipboard.get(Clipboard.Format.UNICODE)

        if raw_text is None or not isinstance(raw_text, str):
            raise ValueError("Clipboard does not contain text")

        hyperlink = transform(raw_text)
        print("Transformed:", hyperlink)

        clipboard.set(Clipboard.Format.HTML, hyperlink)
        clipboard.reload()

    KeySequence("Ctrl+V").apply()
