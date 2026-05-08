# Simplified Enigma Mechanism Demo for M5Stack Tab5 / UIFlow2 Code Mode
# Focus: explain rotor wiring, reflector return path, and stepping.
# Flow animation uses lines only (no animated node dots).
# This is a didactic 8-contact model, not a historically exact 26-contact Enigma.
# Layout: entry at RIGHT -> R -> M -> L -> reflector at LEFT -> back to RIGHT.

import time
import M5
from M5 import Display

# ----------------------------
# Parameters / colors
# ----------------------------
N = 8
ABC = "ABCDEFGH"

BG = 0x0B1020
FG = 0xEAEFF7
DIM = 0x6E7B91
PANEL = 0x121A33
PANEL2 = 0x1A2446
ROTOR_PANEL = [0x13264A, 0x182E52, 0x1D355A]
ROTOR_BORDER = [0x4EA1FF, 0x7CC7FF, 0xA8DEFF]
WIRE = 0x5C6B89
WIRE_HI_FWD = 0x32D1FF
WIRE_HI_REV = 0xFFB14A
REFL = 0x8A63FF
CONTACT = 0xD6E0FF
ENTRY = 0x7CFF6B
EXIT = 0xFF6B9A
BTN = 0x24345A
BTN_HI = 0x35559A
WHITE = 0xFFFFFF
BLACK = 0x000000

# Rotor wirings: local left contact i -> local right contact wiring[i]
ROTOR_R = [2, 5, 7, 1, 6, 0, 3, 4]
ROTOR_M = [4, 6, 1, 7, 0, 3, 5, 2]
ROTOR_L = [1, 7, 5, 0, 6, 2, 4, 3]

# Reflector pairs: one-side fixed paired contacts
REFLECTOR = [3, 5, 7, 0, 6, 1, 4, 2]

ROTOR_NAMES = ["R", "M", "L"]
ROTORS = [ROTOR_R, ROTOR_M, ROTOR_L]

state = {
    "offsets": [0, 0, 0],      # [R, M, L]
    "key": 0,                  # 0..7
    "last_out": 0,
    "trace": None,             # calculated path
    "message": "KEY=A  simplified 8-contact demo",
    "touch_latched": False,
}

# ----------------------------
# Geometry
# ----------------------------
W = 1280
H = 720

title_y = 18

# Right-side entry/lampboard
entry_x = 1210
entry_contact_x = 1175

# Right -> Left layout
rotor_x = [905, 655, 405]       # [R, M, L]
rotor_w = 155
rotor_h = 455
rotor_y = 115
left_contact_dx = 24
right_contact_dx = rotor_w - 24

refl_x = 145
refl_w = 160
refl_h = 455
refl_y = 115
refl_contact_x = refl_x + refl_w - 26   # right edge of reflector

rows_top = 155
row_gap = 46

btn_y = 610
btn_h = 78
buttons = {
    "RESET": (70,  btn_y, 180, btn_h),
    "INFO":  (285, btn_y, 180, btn_h),
    "ENC":   (520, btn_y, 240, btn_h),
    "KEY-":  (815, btn_y, 180, btn_h),
    "KEY+":  (1030, btn_y, 180, btn_h),
}

output_box = (988, 88, 236, 46)

# ----------------------------
# Helpers
# ----------------------------
def row_y(r):
    return rows_top + r * row_gap

def inv_perm(p):
    inv = [0] * len(p)
    for i, v in enumerate(p):
        inv[v] = i
    return inv

INV_ROTORS = [inv_perm(p) for p in ROTORS]

def reflector_pairs():
    seen = set()
    pairs = []
    for a in range(N):
        b = REFLECTOR[a]
        if a in seen or b in seen:
            continue
        seen.add(a)
        seen.add(b)
        pairs.append((a, b))
    return pairs

REFLECTOR_PAIRS = reflector_pairs()

def ch(i):
    return ABC[i % N]

def visible_row(local_index, offset):
    return (local_index + offset) % N

def local_at_row(visible_r, offset):
    return (visible_r - offset) % N

def safe_font():
    try:
        Display.setFont(M5.Lcd.FONTS.EFontCN24)
    except Exception:
        pass

def text(x, y, s, color=FG):
    Display.setCursor(x, y)
    try:
        Display.print(s, color=color)
    except TypeError:
        Display.setTextColor(fgcolor=color, bgcolor=BG)
        Display.print(s)

def center_text_in_rect(x, y, w, h, s, color=FG):
    tx = x + max(6, (w - len(s) * 14) // 2)
    ty = y + (h // 2) - 12
    text(tx, ty, s, color)

def fill_panel(x, y, w, h, color=PANEL, border=PANEL2):
    Display.fillRoundRect(x, y, w, h, 14, color)
    Display.drawRoundRect(x, y, w, h, 14, border)

def fill_panel_emphasized(x, y, w, h, color, border, title_color):
    Display.fillRoundRect(x - 10, y - 10, w + 20, h + 20, 20, 0x0F1833)
    Display.drawRoundRect(x - 10, y - 10, w + 20, h + 20, 20, border)
    Display.drawRoundRect(x - 8, y - 8, w + 16, h + 16, 18, border)
    Display.fillRoundRect(x, y, w, h, 16, color)
    Display.drawRoundRect(x, y, w, h, 16, title_color)

def draw_contact(x, y, color=CONTACT, r=6):
    Display.fillCircle(x, y, r, color)

def draw_pair_label(x, y, a, b, color):
    text(x, y, "{}<->{}".format(ch(a), ch(b)), color)

def hit(x, y, rect):
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh

def lerp(a, b, t_num, t_den):
    return a + ((b - a) * t_num) // t_den

# ----------------------------
# Mechanism
# ----------------------------
def rotor_forward_left_to_right(rotor_idx, visible_in_row):
    offset = state["offsets"][rotor_idx]
    wiring = ROTORS[rotor_idx]
    local_in = local_at_row(visible_in_row, offset)
    local_out = wiring[local_in]
    visible_out = visible_row(local_out, offset)
    return {
        "local_in": local_in,
        "local_out": local_out,
        "visible_out": visible_out,
    }

def rotor_reverse_right_to_left(rotor_idx, visible_in_row):
    offset = state["offsets"][rotor_idx]
    inv = INV_ROTORS[rotor_idx]
    local_in = local_at_row(visible_in_row, offset)
    local_out = inv[local_in]
    visible_out = visible_row(local_out, offset)
    return {
        "local_in": local_in,
        "local_out": local_out,
        "visible_out": visible_out,
    }

def step_rotors_simple():
    # Simplified stepping: odometer style.
    state["offsets"][0] = (state["offsets"][0] + 1) % N
    if state["offsets"][0] == 0:
        state["offsets"][1] = (state["offsets"][1] + 1) % N
        if state["offsets"][1] == 0:
            state["offsets"][2] = (state["offsets"][2] + 1) % N

def compute_trace_without_step():
    # RIGHT entry -> R -> M -> L -> reflector -> L -> M -> R -> RIGHT exit
    k = state["key"]
    trace = {
        "entry_row": k,
        "segments_fwd": [],
        "segments_rev": [],
        "refl_pair": None,
    }

    curr = k
    # forward pass: entering each rotor from RIGHT, so use inverse mapping
    for ridx in [0, 1, 2]:
        out = rotor_reverse_right_to_left(ridx, curr)
        trace["segments_fwd"].append({
            "rotor": ridx,
            "visible_in": curr,
            "visible_out": out["visible_out"],
            "local_in": out["local_in"],
            "local_out": out["local_out"],
        })
        curr = out["visible_out"]

    refl_out = REFLECTOR[curr]
    trace["refl_pair"] = (curr, refl_out)
    curr = refl_out

    # reverse pass: returning through rotors from LEFT to RIGHT, so use forward mapping
    for ridx in [2, 1, 0]:
        out = rotor_forward_left_to_right(ridx, curr)
        trace["segments_rev"].append({
            "rotor": ridx,
            "visible_in": curr,
            "visible_out": out["visible_out"],
            "local_in": out["local_in"],
            "local_out": out["local_out"],
        })
        curr = out["visible_out"]

    trace["exit_row"] = curr
    state["last_out"] = curr
    state["trace"] = trace
    state["message"] = "KEY={}  OUT={}  R/M/L={}/{}/{}".format(
        ch(k), ch(curr),
        ch(state["offsets"][0]), ch(state["offsets"][1]), ch(state["offsets"][2])
    )

# ----------------------------
# Drawing
# ----------------------------
def draw_title():
    text(32, title_y, "ENIGMA MECHANISM DEMO  (8-contact simplified model)", WHITE)
    text(32, 48, "Entry at RIGHT -> R -> M -> L -> Reflector at LEFT -> back to RIGHT", DIM)

def draw_side_letters():
    # Keyboard/lampboard rows at right
    for r in range(N):
        y = row_y(r) - 12
        letter = ch(r)
        color = DIM
        if r == state["key"]:
            color = ENTRY
        if state["trace"] and r == state["last_out"]:
            color = EXIT
        text(entry_x, y, letter, color)
        draw_contact(entry_contact_x, row_y(r), color)
    text(entry_x - 10, 126, "KEY / LAMP", DIM)

def anim_row_y(local_index, old_offset, progress):
    y = row_y(visible_row(local_index, old_offset)) + int(progress * row_gap)
    max_y = row_y(N - 1) + row_gap // 2
    min_y = row_y(0) - row_gap // 2
    total = N * row_gap
    while y > max_y:
        y -= total
    while y < min_y:
        y += total
    return y

def draw_rotor(rotor_idx, anim=None):
    x = rotor_x[rotor_idx]
    y = rotor_y
    w = rotor_w
    h = rotor_h
    offset = state["offsets"][rotor_idx]
    name = ROTOR_NAMES[rotor_idx]
    panel_color = ROTOR_PANEL[rotor_idx]
    border = ROTOR_BORDER[rotor_idx]

    fill_panel_emphasized(x, y, w, h, panel_color, border, border)
    text(x + 14, y + 12, "ROTOR " + name, WHITE)
    text(x + 14, y + 38, "one complete wheel", border)
    text(x + 14, y + 64, "offset " + ch(offset), ENTRY)

    left_x = x + left_contact_dx
    right_x = x + right_contact_dx
    is_anim = anim and anim.get("rotor") == rotor_idx

    for vis_r in range(N):
        yy = row_y(vis_r)
        if not is_anim:
            local_idx = local_at_row(vis_r, offset)
            letter_here = ch(local_idx)
            text(x - 22, yy - 12, letter_here, DIM)
            text(x + w + 10, yy - 12, letter_here, DIM)
            draw_contact(left_x, yy, CONTACT, 5)
            draw_contact(right_x, yy, CONTACT, 5)

    if is_anim:
        old_offset = anim["old_offset"]
        progress = anim["progress"]
        for local_idx in range(N):
            yy = anim_row_y(local_idx, old_offset, progress)
            letter_here = ch(local_idx)
            text(x - 22, yy - 12, letter_here, DIM)
            text(x + w + 10, yy - 12, letter_here, DIM)
            draw_contact(left_x, yy, CONTACT, 5)
            draw_contact(right_x, yy, CONTACT, 5)

        for local_in, local_out in enumerate(ROTORS[rotor_idx]):
            y1 = anim_row_y(local_in, old_offset, progress)
            y2 = anim_row_y(local_out, old_offset, progress)
            Display.drawLine(left_x, y1, right_x, y2, WIRE)

        text(x + 26, y + h - 42, "rotating...", border)
        try:
            Display.drawArc(x + w - 34, y + 40, 18, 0, 300, border)
        except Exception:
            Display.drawCircle(x + w - 34, y + 40, 18, border)
    else:
        for local_in, local_out in enumerate(ROTORS[rotor_idx]):
            vis_in = visible_row(local_in, offset)
            vis_out = visible_row(local_out, offset)
            y1 = row_y(vis_in)
            y2 = row_y(vis_out)
            Display.drawLine(left_x, y1, right_x, y2, WIRE)

def draw_reflector(highlight_pair=None):
    x = refl_x
    y = refl_y
    w = refl_w
    h = refl_h
    fill_panel(x, y, w, h, PANEL, PANEL2)
    text(x + 14, y + 16, "Reflector", WHITE)
    text(x + 14, y + 44, "fixed paired wiring", REFL)
    text(x + 14, y + 72, "same-side contacts are", DIM)
    text(x + 14, y + 96, "hard-wired in pairs", DIM)

    for r in range(N):
        yy = row_y(r)
        text(x + w + 10, yy - 12, ch(r), DIM)
        draw_contact(refl_contact_x, yy, CONTACT, 6)

    lane_xs = [refl_x + 26, refl_x + 52, refl_x + 78, refl_x + 104]
    for idx, (a, b) in enumerate(REFLECTOR_PAIRS):
        y1 = row_y(a)
        y2 = row_y(b)
        lane_x = lane_xs[idx % len(lane_xs)]
        pair_active = highlight_pair is not None and set((a, b)) == set(highlight_pair)
        pair_color = WIRE_HI_FWD if pair_active else REFL
        label_color = pair_color if pair_active else 0xC9B6FF

        # U-shaped fixed jumper that permanently connects two reflector contacts.
        Display.drawLine(refl_contact_x, y1, lane_x, y1, pair_color)
        Display.drawLine(lane_x, y1, lane_x, y2, pair_color)
        Display.drawLine(lane_x, y2, refl_contact_x, y2, pair_color)

        # Pair legend inside the reflector so the wiring is explicit.
        mid_y = ((y1 + y2) // 2) - 12
        draw_pair_label(refl_x + 16, mid_y, a, b, label_color)

        if pair_active:
            draw_contact(refl_contact_x, y1, WIRE_HI_FWD, 7)
            draw_contact(refl_contact_x, y2, WIRE_HI_REV, 7)

def draw_base_connections():
    # Entry -> R (right side)
    for r in range(N):
        y = row_y(r)
        Display.drawLine(entry_contact_x, y, rotor_x[0] + right_contact_dx, y, 0x2D3C5F)

    # Rotor gaps, all right-to-left on forward path
    for r in range(N):
        y = row_y(r)
        Display.drawLine(rotor_x[0] + left_contact_dx, y, rotor_x[1] + right_contact_dx, y, 0x233455)
        Display.drawLine(rotor_x[1] + left_contact_dx, y, rotor_x[2] + right_contact_dx, y, 0x233455)
        Display.drawLine(rotor_x[2] + left_contact_dx, y, refl_contact_x, y, 0x233455)


def draw_output_box():
    x, y, w, h = output_box
    Display.fillRoundRect(x, y, w, h, 12, PANEL)
    Display.drawRoundRect(x, y, w, h, 12, PANEL2)
    if state["trace"]:
        s = "OUTPUT: " + ch(state["trace"]["exit_row"])
        color = EXIT
    else:
        s = "OUTPUT: -"
        color = DIM
    text(x + 18, y + 12, s, color)


def refresh_right_panel():
    # redraw only the right-side labels/contacts and the small output box.
    # Avoid clearing a tall strip here, because that erases nearby path graphics.
    draw_side_letters()
    draw_output_box()

def animate_line(x1, y1, x2, y2, color, steps=5, delay_ms=14, dot_radius=0):
    px = x1
    py = y1
    for i in range(1, steps + 1):
        nx = lerp(x1, x2, i, steps)
        ny = lerp(y1, y2, i, steps)
        Display.drawLine(px, py, nx, ny, color)
        if dot_radius > 0:
            Display.fillCircle(nx, ny, dot_radius, color)
        px = nx
        py = ny
        time.sleep_ms(delay_ms)

def animate_trace_flow():
    tr = state["trace"]
    if not tr:
        return

    refresh_right_panel()
    draw_footer()

    # entry to R (from the right side)
    y = row_y(tr["entry_row"])
    r_right = rotor_x[0] + right_contact_dx
    animate_line(entry_contact_x, y, r_right, y, WIRE_HI_FWD, steps=5, delay_ms=12)

    # forward: R -> M -> L -> reflector
    next_targets = [rotor_x[1] + right_contact_dx, rotor_x[2] + right_contact_dx, refl_contact_x]
    for idx, seg in enumerate(tr["segments_fwd"]):
        ridx = seg["rotor"]
        x = rotor_x[ridx]
        left_x = x + left_contact_dx
        right_x = x + right_contact_dx
        y_in = row_y(seg["visible_in"])
        y_out = row_y(seg["visible_out"])
        animate_line(right_x, y_in, left_x, y_out, WIRE_HI_FWD, steps=6, delay_ms=13)
        animate_line(left_x, y_out, next_targets[idx], y_out, WIRE_HI_FWD, steps=4, delay_ms=12)

    # reflector bounce
    a, b = tr["refl_pair"]
    draw_reflector(highlight_pair=tr["refl_pair"])
    y1 = row_y(a)
    y2 = row_y(b)
    cx = refl_x + 18
    animate_line(refl_contact_x, y1, cx, y1, WIRE_HI_FWD, steps=3, delay_ms=12)
    animate_line(cx, y1, cx, y2, WIRE_HI_FWD, steps=4, delay_ms=14)
    animate_line(cx, y2, refl_contact_x, y2, WIRE_HI_REV, steps=3, delay_ms=12)

    # reverse: L -> M -> R -> output on right side
    prev_source_x = refl_contact_x
    for idx, seg in enumerate(tr["segments_rev"]):
        ridx = seg["rotor"]
        x = rotor_x[ridx]
        left_x = x + left_contact_dx
        right_x = x + right_contact_dx
        y_in = row_y(seg["visible_in"])
        y_out = row_y(seg["visible_out"])

        animate_line(prev_source_x, y_in, left_x, y_in, WIRE_HI_REV, steps=4, delay_ms=12)
        animate_line(left_x, y_in, right_x, y_out, WIRE_HI_REV, steps=6, delay_ms=13)
        prev_source_x = right_x

    y = row_y(tr["exit_row"])
    animate_line(prev_source_x, y, entry_contact_x, y, WIRE_HI_REV, steps=5, delay_ms=12)
    refresh_right_panel()
    draw_footer()

def draw_trace():
    tr = state["trace"]
    if not tr:
        return

    draw_reflector(highlight_pair=tr["refl_pair"])

    # entry to R (from right side)
    y = row_y(tr["entry_row"])
    r_right = rotor_x[0] + right_contact_dx
    Display.drawLine(entry_contact_x, y, r_right, y, WIRE_HI_FWD)
    draw_contact(entry_contact_x, y, ENTRY, 8)

    # forward segments: inside rotor right -> left, then gaps to next rotor's right side
    next_targets = [rotor_x[1] + right_contact_dx, rotor_x[2] + right_contact_dx, refl_contact_x]
    for idx, seg in enumerate(tr["segments_fwd"]):
        ridx = seg["rotor"]
        x = rotor_x[ridx]
        left_x = x + left_contact_dx
        right_x = x + right_contact_dx
        y_in = row_y(seg["visible_in"])
        y_out = row_y(seg["visible_out"])
        Display.drawLine(right_x, y_in, left_x, y_out, WIRE_HI_FWD)
        draw_contact(right_x, y_in, WIRE_HI_FWD, 7)
        draw_contact(left_x, y_out, WIRE_HI_FWD, 7)
        if idx < len(next_targets):
            Display.drawLine(left_x, y_out, next_targets[idx], y_out, WIRE_HI_FWD)

    # reflector highlight
    a, b = tr["refl_pair"]
    y1 = row_y(a)
    y2 = row_y(b)
    cx = refl_x + 18
    Display.drawLine(refl_contact_x, y1, cx, y1, WIRE_HI_FWD)
    Display.drawLine(cx, y1, cx, y2, WIRE_HI_FWD)
    Display.drawLine(cx, y2, refl_contact_x, y2, WIRE_HI_REV)
    draw_contact(refl_contact_x, y1, WIRE_HI_FWD, 7)
    draw_contact(refl_contact_x, y2, WIRE_HI_REV, 7)

    # reverse segments: reflector -> L -> M -> R -> lampboard, inside rotor left -> right
    gap_targets = [rotor_x[1] + left_contact_dx, rotor_x[0] + left_contact_dx, entry_contact_x]
    for idx, seg in enumerate(tr["segments_rev"]):
        ridx = seg["rotor"]
        x = rotor_x[ridx]
        left_x = x + left_contact_dx
        right_x = x + right_contact_dx
        y_in = row_y(seg["visible_in"])
        y_out = row_y(seg["visible_out"])

        if ridx == 2:
            Display.drawLine(refl_contact_x, y_in, left_x, y_in, WIRE_HI_REV)
        else:
            prev_left = gap_targets[idx - 1]
            Display.drawLine(prev_left, y_in, left_x, y_in, WIRE_HI_REV)

        Display.drawLine(left_x, y_in, right_x, y_out, WIRE_HI_REV)
        draw_contact(left_x, y_in, WIRE_HI_REV, 7)
        draw_contact(right_x, y_out, WIRE_HI_REV, 7)

        target_x = gap_targets[idx]
        Display.drawLine(right_x, y_out, target_x, y_out, WIRE_HI_REV)

    y = row_y(tr["exit_row"])
    draw_contact(entry_contact_x, y, EXIT, 8)
    draw_output_box()

def draw_buttons():
    for name, rect in buttons.items():
        x, y, w, h = rect
        color = BTN_HI if name == "ENC" else BTN
        Display.fillRoundRect(x, y, w, h, 16, color)
        Display.drawRoundRect(x, y, w, h, 16, 0x5577C0)
        center_text_in_rect(x, y, w, h, name, WHITE)

def draw_footer():
    Display.fillRect(0, 540, W, 60, BG)
    text(38, 574, "Selected input key: " + ch(state["key"]), ENTRY)
    text(320, 574, "R/M/L offsets: {}/{}/{}".format(
        ch(state["offsets"][0]), ch(state["offsets"][1]), ch(state["offsets"][2])
    ), FG)
    text(38, 544, "Reflector labels show fixed letter-pairs; this demo uses 8 contacts so the wiring stays visible.", DIM)
    Display.fillRect(0, 76, W, 28, BG)
    text(38, 80, state["message"], FG)

def draw_rotor_dividers():
    left_edges = [refl_x + refl_w + 18, rotor_x[2] + rotor_w + 18, rotor_x[1] + rotor_w + 18, rotor_x[0] + rotor_w + 18]
    for x in left_edges:
        Display.fillRect(x, rotor_y - 20, 8, rotor_h + 40, 0x0F1833)
    text(refl_x + 8, refl_y + refl_h + 14, "fixed reflector", REFL)
    text(rotor_x[2] + 8, rotor_y + rotor_h + 14, "each box = one rotor", DIM)

def draw_static_scene():
    Display.clear(BG)
    draw_title()
    draw_side_letters()
    draw_output_box()
    draw_base_connections()
    draw_rotor_dividers()
    draw_reflector()
    draw_buttons()
    draw_footer()

def redraw_full(show_trace=True):
    draw_static_scene()
    for i in range(3):
        draw_rotor(i)
    if show_trace:
        draw_trace()
    draw_footer()

def clear_rotor_area(rotor_idx):
    x = rotor_x[rotor_idx]
    y = rotor_y
    w = rotor_w
    h = rotor_h
    Display.fillRect(x - 36, y - 22, w + 72, h + 54, BG)

def redraw_rotor_only(rotor_idx, anim=None):
    clear_rotor_area(rotor_idx)
    draw_rotor(rotor_idx, anim=anim)

def reset_demo():
    state["offsets"] = [0, 0, 0]
    state["key"] = 0
    state["last_out"] = 0
    state["trace"] = None
    state["message"] = "Reset  KEY=A"

def animate_single_rotor_step(rotor_idx):
    old_offset = state["offsets"][rotor_idx]
    state["message"] = "stepping rotor {}".format(ROTOR_NAMES[rotor_idx])
    draw_footer()

    # redraw only the rotating rotor panel to reduce whole-screen flicker
    for p in [0.0, 0.35, 0.7, 1.0]:
        redraw_rotor_only(rotor_idx, anim={"rotor": rotor_idx, "old_offset": old_offset, "progress": p})
        time.sleep_ms(45)

    state["offsets"][rotor_idx] = (old_offset + 1) % N
    redraw_rotor_only(rotor_idx)

def animate_and_build_trace():
    state["trace"] = None
    redraw_full(show_trace=False)

    animate_single_rotor_step(0)
    if state["offsets"][0] == 0:
        animate_single_rotor_step(1)
        if state["offsets"][1] == 0:
            animate_single_rotor_step(2)

    compute_trace_without_step()
    animate_trace_flow()

# ----------------------------
# Input
# ----------------------------
def on_tap(x, y):
    if hit(x, y, buttons["KEY-"]):
        state["key"] = (state["key"] - 1) % N
        state["trace"] = None
        state["message"] = "KEY=" + ch(state["key"])
        redraw_full(show_trace=False)
        return

    if hit(x, y, buttons["KEY+"]):
        state["key"] = (state["key"] + 1) % N
        state["trace"] = None
        state["message"] = "KEY=" + ch(state["key"])
        redraw_full(show_trace=False)
        return

    if hit(x, y, buttons["ENC"]):
        animate_and_build_trace()
        return

    if hit(x, y, buttons["RESET"]):
        reset_demo()
        redraw_full(show_trace=False)
        return

    if hit(x, y, buttons["INFO"]):
        state["message"] = "Reflector is fixed: hard-wired pairs (like A<->D) send current back through the same rotors."
        draw_footer()
        return

# ----------------------------
# Main
# ----------------------------
def setup():
    M5.begin()
    Display.setRotation(1)
    Display.setTextColor(fgcolor=FG, bgcolor=BG)
    safe_font()
    redraw_full(show_trace=False)

def loop():
    M5.update()

    if M5.Touch.getCount():
        if not state["touch_latched"]:
            x = M5.Touch.getX()
            y = M5.Touch.getY()
            on_tap(x, y)
            state["touch_latched"] = True
    else:
        state["touch_latched"] = False

    time.sleep_ms(20)

if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except Exception:
            print(e)
