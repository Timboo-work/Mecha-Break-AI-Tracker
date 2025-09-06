import time
import re
import json
from collections import OrderedDict
import psutil
from pathlib import Path
import os
import sys
import ctypes

# =======================
# Disable QuickEdit Mode (Windows)
# =======================
def disable_quickedit():
    if sys.platform != "win32":
        return
    kernel32 = ctypes.windll.kernel32
    hStdin = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
    mode = ctypes.c_uint()
    if kernel32.GetConsoleMode(hStdin, ctypes.byref(mode)):
        new_mode = mode.value & ~0x40  # Clear QuickEdit bit
        kernel32.SetConsoleMode(hStdin, new_mode)

disable_quickedit()

# =======================
# Colors
# =======================
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

MAX_PLAYERS = 50

MECHA_NAMES = {
    100010: "Skyraider",
    100003: "Alysnes",
    100001: "Falcon",
    100004: "Tricera",
    100012: "Welkin",
    100005: "Narukami",
    100018: "Hurricane",
    100007: "Luminae",
    100015: "Aquila",
    100008: "Pinaka",
    100016: "Stego",
    100002: "Panther",
    100017: "Stellaris",
    100009: "Inferno",
    100006: "Serenith",
}

# =======================
# Regex
# =======================
player_line = re.compile(
    r"playerId\s*:\s*(?P<playerId>\d+),\s*"
    r"displayName\s*:\s*(?P<displayName>[^,]+),\s*"
    r"mechaId\s*:\s*(?P<mechaId>\d+),\s*"
    r"pilotId\s*:\s*\d+,\s*"
    r"ready\s*:\s*\w+,\s*"
    r"isAi\s*:\s*(?P<isAi>\w+)"
)
json_line = re.compile(r"\{.*\}$")

players = OrderedDict()

# =======================
# Functions
# =======================
def find_latest_mechabreak_log_file():
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            if proc.info['name'] and "MechaBREAK" in proc.info['name']:
                exe_path = proc.info['exe']
                exe_folder = os.path.dirname(exe_path)
                parent_folder = os.path.dirname(exe_folder)
                log_base = os.path.join(parent_folder, "logs", "MechaBREAK")
                if not os.path.exists(log_base):
                    return None

                subfolders = [f for f in Path(log_base).iterdir() if f.is_dir()]
                if not subfolders:
                    return None
                latest_folder = max(subfolders, key=lambda f: f.stat().st_ctime)

                files = [f for f in latest_folder.iterdir() if f.is_file()]
                if not files:
                    return None
                latest_file = max(files, key=lambda f: f.stat().st_ctime)
                return str(latest_file)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def reset_players():
    global players
    players.clear()
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== Player tracking reset ===\n")


def add_or_update_player(name, data):
    if not name:
        return

    # Update only if new or changed
    if name in players:
        existing = players[name]
        changed = False
        if "ready" in data and data["ready"] != existing.get("ready"):
            existing["ready"] = data["ready"]
            changed = True
        if "mechaId" in data and data["mechaId"] != existing.get("mechaId"):
            existing["mechaId"] = data["mechaId"]
            changed = True
        if changed:
            print_players()
        return

    if len(players) >= MAX_PLAYERS:
        old_name, _ = players.popitem(last=False)
        print(f"Removed old player {old_name}")
    players[name] = data
    print_players()


def print_players():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n=== Current Tracked Players ===")

    sorted_players = sorted(
        players.items(),
        key=lambda kv: (kv[1].get("isAi", True), kv[0] or "")
    )

    for name, pdata in sorted_players:
        is_ai = pdata.get("isAi", None)
        ready = pdata.get("ready", None)
        mecha_id = pdata.get("mechaId")
        mecha_name = MECHA_NAMES.get(mecha_id, f"Unknown({mecha_id})")

        display = name
        if is_ai is False:
            display = f"{RED}{display}{RESET}"
        elif is_ai is True:
            display = f"{YELLOW}{display}{RESET}"

        print(f"{display}, mecha={mecha_name}, isAi={is_ai}, ready={ready}")
    print("================================\n")


# =======================
# Main
# =======================
logfile = find_latest_mechabreak_log_file()
if not logfile:
    print("Could not find the latest MechaBREAK log file!")
    time.sleep(5)
    exit()

print(f"Tracking log file: {logfile}")

with open(logfile, "r", encoding="utf-8", errors="ignore") as f:
    f.seek(0, 2)
    while True:
        try:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue

            if "GAME_S2C_QUERY_COMBAT_RECORD_RESULT" in line:
                reset_players()
                continue

            if "UIWarPreparePlayer.cs" in line and "playerId" in line:
                m = player_line.search(line)
                if m:
                    name = m.group("displayName")
                    data = {
                        "playerId": m.group("playerId"),
                        "mechaId": int(m.group("mechaId")),
                        "isAi": m.group("isAi") == "True",
                    }
                    add_or_update_player(name, data)

            elif "UIWarPrepareModule.cs" in line:
                m = json_line.search(line)
                if m:
                    try:
                        payload = json.loads(m.group(0))
                        display_name = payload.get("displayName")
                        if not display_name:
                            continue
                        data = {
                            "ready": payload.get("ready"),
                            "mechaId": payload.get("aiMechaDiy", {}).get("mechaId"),
                        }
                        add_or_update_player(display_name, data)
                    except json.JSONDecodeError:
                        pass
        except KeyboardInterrupt:
            print("\nIgnoring accidental Ctrl+C. Tracker still running.")
