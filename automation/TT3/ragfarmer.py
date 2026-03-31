"""
Ragnarok X - Auto-Farmer
Farms Doomsday Battle Round 2 (Normal) and detects a target item drop.

Requirements:
    pip install pyautogui opencv-python Pillow pygetwindow

Usage:
    python ragfarmer.py                # Start farming
    python ragfarmer.py --calibrate    # Show live mouse coords (no clicks)
    python ragfarmer.py --test-detect  # Test item detection on current screen

FAILSAFE: Slam the mouse into the TOP-LEFT corner of your screen to abort instantly.
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import pydirectinput
import pygetwindow as gw

# SET resolution: 1600x900
# ============================================================
#  CONFIGURATION — edit these two lines to switch targets
# ============================================================

#TARGET_IMAGE   = "Blessing_lock.PNG"  #"mask.PNG"   # Swap to "mask.PNG" for the real run
TARGET_IMAGE = "bapho_mask.PNG"
VOUCHER_AMOUNT = 1600             # Vouchers to offer  (100 to test, 1600 for real)

# How confident the match needs to be (0.0–1.0).
# Start at 0.75 and adjust: lower if it misses the item, higher if it false-triggers.
CONFIDENCE = .65

#============================================================
#  WINDOW & TIMING
# ============================================================

GAME_TITLE    = "Ragnarok X"
T_MENU        = 1.5    # seconds to wait after each menu/nav click
T_LOAD        = 10.0    # seconds to wait for instance to finish loading
T_COMBAT_POLL = 5.0    # seconds between "is the boss dead?" checks
T_MAX_FIGHT   = 30    # give up on a fight after this many seconds (10 min)

# --- Cutscene + movement ---
# How long (seconds) to hold W after the cutscene ends to walk to the boss.
# Increase if the bot doesn't reach the boss; decrease if it overshoots.
T_WALK_TO_BOSS    = 0.0

# Max seconds to wait for the cutscene to end before giving up and walking anyway.
T_CS_WAIT_MAX     = 15.0

# The SKIP button pixel goes bright white during the cutscene and turns dark
# when the game world appears. We use this to detect when the CS has ended.
# If detection is unreliable, increase CS_BRIGHT_THRESHOLD (default 200).
CS_DETECT_POS     = (1468, 69)   # same as BTL_SKIP — top-right corner
CS_BRIGHT_THRESHOLD = 200        # pixel brightness above this = cutscene still showing

# ============================================================
#  CLICK COORDINATES  (relative to game CLIENT area)
#
#  Calibrated for a 1806×738 client area.
#  Run  python ragfarmer.py --calibrate  then hover over any
#  button to see its exact client coordinates, and update here.
# ============================================================

# --- Menu navigation ---
NAV_CARNIVAL    = (1115,  49)   # "Carnival" HUD button (top-right)
NAV_TRIAL       = ( 189, 157)   # "Trial Illusion" icon in Carnival map
NAV_GONOW       = ( 312, 749)   # "Go Now" button in Trial Illusion popup
NAV_DOOMSDAY    = ( 1101, 273)   # "Doomsday Battle" (option 01)
NAV_ROUND2      = ( 508, 405)   # Round 2 card (middle card)
NAV_NORMAL      = ( 898, 128)
#NAV_NORMAL  = ( 1171, 120)   # "Normal" difficulty tab
NAV_UNLOCK      = ( 1264, 676)   # "Unlock the Illusion" button

# --- Battle ---
BTL_SKIP        = (1448,  55)   # "SKIP" cutscene button (top-right)

# --- Reward screen ---
RWD_VOUCHER     = ( 804, 439)   # Realm Voucher input field (opens numpad)
RWD_OFFER       = ( 803, 517)   # "Offer" button
RWD_CLOSE       = (1471, 163)   # X button to close reward dialog

# --- Numpad (appears after clicking the voucher input field) ---
# Layout:  [ 1 ][ 2 ][ 3 ][ X ]
#          [ 4 ][ 5 ][ 6 ][ 0 ]
#          [ 7 ][ 8 ][ 9 ][ ✓ ]
NUMPAD = {
    "1": ( 664, 354), "2": ( 754, 354), "3": ( 845, 354), "X": ( 939, 354),
    "4": ( 667, 453), "5": ( 754, 453), "6": ( 845, 453), "0": ( 939, 453),
    "7": ( 655, 553), "8": ( 754, 553), "9": ( 845, 553), "V": ( 939, 553),
    #                                                       ^ green checkmark
}

# --- Post-battle ---
POST_LEAVE      = (1305, 234)   # "Leave" button
LEAVE_CONFIRM   = ( 926, 581)   # Confirm close

# --- Reward screen detection ---
# We sample this pixel; on the reward screen it should be gold/amber.
REWARD_PIXEL    = (110, 335)
REWARD_COLOR = (126, 92, 65)

# --- Item search region (the 3 locked item slots at top of reward dialog) ---
# (left, top, width, height) in client coordinates
ITEM_REGION     = (166, 153, 1200, 450)


# ============================================================
#  WINDOW HELPERS
# ============================================================

def get_window():
    wins = gw.getWindowsWithTitle(GAME_TITLE)
    if not wins:
        raise RuntimeError(
            f'Game window "{GAME_TITLE}" not found — is the game running?'
        )
    return wins[0]


def focus():
    """Bring the game window to the foreground."""
    win = get_window()
    try:
        win.activate()
    except Exception:
        pass
    time.sleep(0.25)


def client_origin():
    """
    Return the (x, y) screen position of the top-left of the game's
    client area (excluding the Windows title bar and border).
    """
    win = get_window()
    return win.left + 8, win.top + 31  # standard Win10/11 decoration


def to_screen(cx, cy):
    ox, oy = client_origin()
    return ox + cx, oy + cy


def gclick(cx, cy, pause=0.1):
    """Click at a game-client coordinate."""
    focus()
    sx, sy = to_screen(cx, cy)
    pyautogui.click(sx, sy)
    time.sleep(pause)


def wait_until(condition_fn, timeout, poll_interval=0.5, label=""):
    """
    Poll condition_fn() every poll_interval seconds until truthy or timeout.
    Checks immediately on entry. Returns True on success, False on timeout.
    """
    tag = f"[{label}] " if label else ""
    deadline = time.time() + timeout
    while True:
        if condition_fn():
            return True
        remaining = deadline - time.time()
        if remaining <= 0:
            print(f"  {tag}Timed out after {timeout}s.")
            return False
        time.sleep(min(poll_interval, remaining))


# ============================================================
#  REWARD SCREEN DETECTION
# ============================================================

def is_reward_visible():
    """
    Detect the reward screen by sampling the pixel at the Offer button.
    On the reward screen it should be a gold/amber colour.
    """
    sx, sy = to_screen(*REWARD_PIXEL)
    r, g, b = pyautogui.pixel(sx, sy)
    return (110 < r < 150) and (85 < g < 185) and (b < 100)


# ============================================================
#  ITEM DETECTION  (OpenCV template matching)
# ============================================================

def find_item(template_path, save_debug=False):
    """
    Capture the item-slot region of the reward screen and run
    normalised cross-correlation template matching.

    The templates used (e.g. mask_BAPHO_locked.PNG) already have the
    lock overlay composited in, so matching is done against the full icon
    with no pixels excluded.

    Returns (confidence, client_x, client_y).
    confidence is 0.0–1.0; higher = better match.

    If save_debug=True, writes debug_match.png showing the best
    match location — useful for tuning CONFIDENCE and ITEM_REGION.
    """
    ox, oy = client_origin()
    rl, rt, rw, rh = ITEM_REGION

    # Capture the search region
    screenshot = pyautogui.screenshot(region=(ox + rl, oy + rt, rw, rh))
    haystack = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Load template
    needle = cv2.imread(str(template_path))
    if needle is None:
        raise FileNotFoundError(f"Cannot load template image: {template_path}")

    # If the template is larger than the search area, scale it down
    nh, nw = needle.shape[:2]
    hh, hw = haystack.shape[:2]
    if nw > hw or nh > hh:
        scale = min(hw / nw, hh / nh) * 0.9
        needle = cv2.resize(needle, (int(nw * scale), int(nh * scale)))
        nh, nw = needle.shape[:2]

    nh2, nw2 = needle.shape[:2]
    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, loc = cv2.minMaxLoc(result)

    # Convert match location back to client coordinates
    found_cx = rl + loc[0]
    found_cy = rt + loc[1]

    # Always save a timestamped debug image regardless of save_debug flag
    debug_dir = Path(__file__).parent / "debug_matches"
    debug_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms precision
    detected = "HIT" if confidence >= CONFIDENCE else "MISS"
    debug_path = debug_dir / f"debug_match_{ts}_{detected}_{confidence:.3f}.png"

    debug = haystack.copy()
    cv2.rectangle(debug, loc, (loc[0] + nw2, loc[1] + nh2), (0, 255, 0), 2)
    cv2.imwrite(str(debug_path), debug)
    print(f"    debug image saved → {debug_path.name}")

    if save_debug:
        cv2.imwrite(str(Path(__file__).parent / "debug_template.png"), needle)
        print(f"    debug_template.png saved")

    return confidence, found_cx, found_cy


# ============================================================
#  NUMPAD INPUT
# ============================================================

def enter_vouchers(amount: int):
    """
    Click the voucher input to open the numpad, clear it,
    type each digit of `amount`, then confirm with the checkmark.
    """
    gclick(*RWD_VOUCHER)
    time.sleep(0.7)

    # Clear anything already in the field
    gclick(*NUMPAD["X"])
    time.sleep(0.3)

    # Type each digit
    for ch in str(amount):
        gclick(*NUMPAD[ch])
        time.sleep(0.2)

    # Confirm (green checkmark)
    gclick(*NUMPAD["V"])
    time.sleep(0.5)


# ============================================================
#  FARMING STEPS
# ============================================================

def navigate_to_instance():
    print("  Navigating to instance...")
    focus()
    time.sleep(0.5)
    gclick(*NAV_CARNIVAL)
    time.sleep(T_MENU)
    gclick(*NAV_TRIAL)
    time.sleep(T_MENU)
    gclick(*NAV_GONOW)
    time.sleep(T_MENU)
    gclick(*NAV_DOOMSDAY)
    time.sleep(T_MENU)
    gclick(*NAV_ROUND2)
    #gclick(*NAV_NORMAL)
    time.sleep(0.2)
    gclick(*NAV_UNLOCK)
    time.sleep(T_MENU)


def is_cutscene_showing():
    """
    Return True if the cutscene SKIP button is visible (bright white pixel).
    Returns False once the game world has taken over (pixel goes dark).
    """
    sx, sy = to_screen(*CS_DETECT_POS)
    r, g, b = pyautogui.pixel(sx, sy)
    brightness = (r + g + b) / 3
    return brightness > CS_BRIGHT_THRESHOLD


def skip_cutscene():
    """
    Click SKIP until the cutscene pixel goes dark, then give the
    game a moment to finish transitioning.
    """
    print("  Skipping cutscene...")
    for _ in range(3):
        gclick(*BTL_SKIP)
        time.sleep(0.4)


def wait_for_cutscene_end():
    print("  Waiting for cutscene to end...")
    result = wait_until(
        lambda: not is_cutscene_showing(),
        timeout=T_CS_WAIT_MAX,
        poll_interval=0.3,
        label="cutscene_end"
    )
    if result:
        print("  Cutscene ended — game world detected.")
        time.sleep(0.05)
    return result


def walk_to_boss():
    """
    Hold W for T_WALK_TO_BOSS seconds to move the character toward the boss,
    then release. Adjust T_WALK_TO_BOSS in config if the distance is wrong.
    Uses pydirectinput so the keypress reaches the game's DirectInput handler.
    """
    print(f"  Walking to boss (holding W for {T_WALK_TO_BOSS}s)...")
    focus()
    pydirectinput.keyDown("w")
    time.sleep(T_WALK_TO_BOSS)
    pydirectinput.keyUp("w")
    time.sleep(0.3)


def wait_for_boss_death():
    print("  Waiting for boss to die...")
    start = time.time()

    def check():
        if is_reward_visible():
            print("  Reward screen detected.")
            return True
        elapsed = time.time() - start
        remaining = T_MAX_FIGHT - elapsed
        print(f"    Still fighting... ({elapsed:.0f}s elapsed, {remaining:.0f}s remaining)")
        return False

    return wait_until(check, timeout=T_MAX_FIGHT,
                      poll_interval=T_COMBAT_POLL, label="boss_death")


def handle_rewards(template_path):
    """
    Check the reward screen for the target item and offer vouchers if found.
    Returns True if the target item was found, False otherwise.
    Does NOT close the reward screen — the caller always does that.
    """
    time.sleep(1.0)
    confidence, fx, fy = find_item(template_path, save_debug=True)
    print(f"  Match confidence: {confidence:.3f}  (threshold: {CONFIDENCE})")

    if confidence >= CONFIDENCE:
        print(f"  ✓ TARGET ITEM FOUND!")
        enter_vouchers(VOUCHER_AMOUNT)
        time.sleep(0.5)
        gclick(*RWD_OFFER)
        time.sleep(2.5)
        return True
    else:
        print("  ✗ Target item not in drops this run.")
        return False


# ============================================================
#  MAIN FARMING LOOP
# ============================================================

def farm(template_path):
    run = 0
    while True:
        run += 1
        print(f"\n{'=' * 40}")
        print(f"  Run #{run}  |  Target: {template_path.name}")
        print(f"{'=' * 40}")

        run_start = time.time()
        navigate_to_instance()

        print(f"  Waiting for instance to load ({T_LOAD}s)...")
        time.sleep(T_LOAD)

        skip_cutscene()
        wait_for_cutscene_end()
        #walk_to_boss()

        print("  Starting combat (pressing K)...")
        focus()
        pydirectinput.press("k")
        time.sleep(1.0)

        if not wait_for_boss_death():
            print(f"  Leaving after timeout... (run time: {time.time() - run_start:.0f}s)")
            gclick(*POST_LEAVE)
            time.sleep(6.0)
            continue

        found = handle_rewards(template_path)

        # Always close the reward screen before doing anything else
        print("  Closing reward screen...")
        gclick(*RWD_CLOSE)
        time.sleep(1.5)

        run_elapsed = time.time() - run_start
        print(f"  Run #{run} completed in {run_elapsed:.0f}s")

        if found:
            print("\n" + "★" * 42)
            print("  TARGET ITEM SECURED — FARMING COMPLETE!")
            print("★" * 42)
            break

        print("  Leaving instance...")
        time.sleep(2.0)
        gclick(*POST_LEAVE)
        time.sleep(1.0)
        gclick(*LEAVE_CONFIRM)
        time.sleep(10.0)


# ============================================================
#  UTILITY MODES
# ============================================================

def calibration_mode():
    """
    Show live mouse position relative to the game client area.
    Hover over any button to see the coordinates to put in COORDS.
    No clicks are made. Press Ctrl+C to exit.
    """
    print("═" * 50)
    print("  CALIBRATION MODE  —  no clicks will be made")
    print("  Hover the mouse over any game element.")
    print("  Press Ctrl+C to exit.")
    print("═" * 50 + "\n")

    last = None
    while True:
        try:
            mx, my = pyautogui.position()
            ox, oy = client_origin()
            cx, cy = mx - ox, my - oy
            r, g, b = pyautogui.pixel(mx, my)
            pos = (cx, cy)
            if pos != last:
                print(f"  Client ({cx:5d}, {cy:4d})   Screen ({mx}, {my})   "
                      f"RGB ({r:3d}, {g:3d}, {b:3d})")
                last = pos
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nCalibration mode exited.")
            break


def test_detection_mode(item_template_path):
    """
    Run item detection once on whatever is currently on screen
    and print the result. Saves debug_match.png for visual inspection.
    Make sure the reward screen is visible before running this.
    """
    print("═" * 50)
    print(f"  DETECTION TEST  —  template: {item_template_path.name}")
    print("  Reward screen must be visible in-game.")
    print("  Starting in 3 seconds...")
    print("═" * 50)
    time.sleep(3.0)

    confidence, fx, fy = find_item(item_template_path, save_debug=True)

    print(f"\n  Confidence : {confidence:.4f}")
    print(f"  Location   : client ({fx}, {fy})")
    print(f"  Threshold  : {CONFIDENCE}")
    print(f"  Result     : {'✓ FOUND' if confidence >= CONFIDENCE else '✗ NOT FOUND'}")
    print(f"\n  Open debug_match.png to see where the best match landed.")
    print("  If the green box is wrong, adjust ITEM_REGION or CONFIDENCE.")


# ============================================================
#  ENTRY POINT
# ============================================================

if __name__ == "__main__":
    pyautogui.FAILSAFE = True  # top-left corner = emergency stop
    pyautogui.PAUSE = 0.05

    parser = argparse.ArgumentParser(description="Ragnarok X Auto-Farmer")
    parser.add_argument("--calibrate", action="store_true",
                        help="Live mouse coordinate display (no clicks)")
    parser.add_argument("--test-detect", action="store_true",
                        help="Test item detection on current screen")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    template_path = script_dir / TARGET_IMAGE

    if not args.calibrate and not template_path.exists():
        print(f"ERROR: Template image not found: {template_path}")
        print(f"Place '{TARGET_IMAGE}' in the same folder as this script.")
        sys.exit(1)

    if args.calibrate:
        calibration_mode()
    elif args.test_detect:
        test_detection_mode(template_path)
    else:
        print("Ragnarok X Auto-Farmer")
        print(f"  Target image : {TARGET_IMAGE}")
        print(f"  Vouchers     : {VOUCHER_AMOUNT}")
        print(f"  Confidence   : {CONFIDENCE}")
        print(f"\nStarting in 5 seconds — switch to Ragnarok X now!")
        print("FAILSAFE: slam mouse to the TOP-LEFT corner to abort.\n")
        time.sleep(5)
        farm(template_path)
