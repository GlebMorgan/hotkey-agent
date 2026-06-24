from actions.special_paste import special_paste
from hotkey_agent import HotkeyAgent


if __name__ == "__main__":
    with HotkeyAgent() as agent:
        agent.register_action("Ctrl+Alt+V", special_paste)
        agent.run()
