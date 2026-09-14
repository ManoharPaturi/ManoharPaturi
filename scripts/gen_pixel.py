#!/usr/bin/env python3
"""Generate assets/pixel-hero.svg — pixel-art name banner + signal-lab scene.

Everything is 8x8 blocks on a grid; run with --ascii to preview the
composition as text before rendering.
"""
import sys

S = 8  # block size in px
W = 126  # grid width
NAME_H = 12  # name band height (rows)
SCENE_H = 56  # scene height (rows)
H = NAME_H + SCENE_H

BG = "#0D1117"
WALL = "#11151D"
WALL_DK = "#0B0F16"
FLOOR = "#151B26"
FLOOR_LN = "#1B2230"
GRID = "#161B22"
FRAME = "#2A3245"
DESK = "#3B3148"
DESK_DK = "#2E2640"
SCREEN = "#0A1626"
BLUE = "#58A6FF"
PURPLE = "#A371F7"
PINK = "#F778BA"
GREEN = "#3FB950"
YELLOW = "#FEBC2E"
ORANGE = "#F0883E"
CREAM = "#E8D8A8"
SKIN = "#E8B98A"
HAIR = "#17171F"
HOOD = "#A371F7"
HOOD_DK = "#8A58D6"
PANTS = "#252D3D"
STEEL = "#8B949E"
TEXT_DIM = "#30363D"

px = []  # (gx, gy, color)


def P(x, y, c, w=1, h=1):
    px.append((x, y, c, w, h))


# ---------- 5x7 pixel font ----------
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "11001", "10101", "10011", "10011", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
}


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(min(255, max(0, round(a[k] + (b[k] - a[k]) * t))) for k in range(3))


def hex2rgb(hx):
    return tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))


def rgb2hex(rgb):
    return "#%02X%02X%02X" % rgb


def draw_name(y0):
    word = "MANOHAR PATURI"
    glyph_w = 6  # 5 cols + 1 gap
    total = len(word) * glyph_w - 1
    x0 = (W - total) // 2
    c1, c2 = hex2rgb(PURPLE), hex2rgb(PINK)
    for i, ch in enumerate(word):
        if ch == " ":
            continue
        t = (i * glyph_w) / max(1, total - 1)
        col = rgb2hex(lerp(c1, c2, t))
        for ry, row in enumerate(FONT[ch]):
            for rx, bit in enumerate(row):
                if bit == "1":
                    P(x0 + i * glyph_w + rx, y0 + ry, col)
    # underline accent, same gradient idea
    uy = y0 + 9
    for gx in range(x0, x0 + total):
        t = (gx - x0) / max(1, total - 1)
        P(gx, uy, rgb2hex(lerp(c1, c2, t)))

def wave(x0, x1, y_mid, color, amp=2, period=6, phase=0, thick=1):
    for gx in range(x0, x1):
        yy = y_mid + round(amp * ((gx + phase) % period < period // 2) * -1 + amp * ((gx + phase) % period >= period // 2))
        # simple square-ish wave; soften with sine-like steps
        for k in range(thick):
            P(gx, yy + k, color)


def sine(x0, x1, y_mid, color, amp=3, period=10, phase=0):
    import math
    prev = None
    for gx in range(x0, x1):
        yy = y_mid + round(amp * math.sin((gx + phase) * 2 * math.pi / period))
        if prev is not None and abs(yy - prev) > 1:
            for k in range(min(yy, prev), max(yy, prev) + 1):
                P(gx - 1, k, color)
        P(gx, yy, color)
        prev = yy


def draw_scene(oy):
    Y = lambda v: oy + v  # local scene row -> absolute grid row

    # wall + floor
    P(0, Y(0), WALL, W, 48)
    # subtle wall texture: sparse darker dots
    for gx in range(3, W, 11):
        P(gx, Y(6 + (gx * 5) % 34), WALL_DK)
    P(0, Y(48), FLOOR_LN, W, 1)
    P(0, Y(49), FLOOR, W, 7)
    for gx in range(0, W, 9):
        P(gx, Y(51), FLOOR_LN, 4, 1)

    # --- ceiling light ---
    P(58, Y(0), FRAME, 2, 2)
    P(54, Y(2), YELLOW, 10, 1)
    P(54, Y(3), "#4A3B12", 10, 1)

    # --- window (night sky, moon) ---
    wx, wy, ww, wh = 4, 4, 20, 15
    P(wx, Y(wy), FRAME, ww, wh)
    P(wx + 1, Y(wy + 1), "#0A1122", ww - 2, wh - 2)
    P(wx + 2, Y(wy + 2), "#0D1830", 8, 6)  # cloud band
    # moon
    P(wx + 14, Y(wy + 3), CREAM, 3, 3)
    P(wx + 14, Y(wy + 3), "#0D1830")  # crescent bite
    P(wx + 13, Y(wy + 4), CREAM)
    # stars
    for sx, sy in [(4, 3), (9, 6), (15, 9), (6, 10), (12, 2)]:
        P(wx + sx, Y(wy + sy), CREAM)
    P(wx + 10, Y(wy + 1), FRAME, 1, wh - 2)  # cross bar
    P(wx + 1, Y(wy + 8), FRAME, ww - 2, 1)

    # --- poster: neural net doodle ---
    px_, py_, pw, ph = 100, 4, 17, 19
    P(px_, Y(py_), FRAME, pw, ph)
    P(px_ + 1, Y(py_ + 1), "#12182A", pw - 2, ph - 2)
    nodes = [(4, 4), (4, 9), (4, 14), (10, 6), (10, 12), (14, 9)]
    for (x1, y1), (x2, y2) in [
        (nodes[0], nodes[3]), (nodes[0], nodes[4]), (nodes[1], nodes[3]),
        (nodes[1], nodes[4]), (nodes[2], nodes[4]), (nodes[3], nodes[5]), (nodes[4], nodes[5]),
    ]:
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for s in range(steps + 1):
            P(px_ + x1 + round((x2 - x1) * s / steps), Y(py_ + y1 + round((y2 - y1) * s / steps)), TEXT_DIM)
    for i, (nx, ny) in enumerate(nodes):
        P(px_ + nx - 1, Y(py_ + ny - 1), BLUE if i % 2 else PINK, 2, 2)
    P(px_ + 3, Y(py_ + 16), PURPLE, 11, 1)  # caption strip

    # --- shelf with books + duck ---
    sx, sy = 58, 15
    P(sx, Y(sy), FRAME, 24, 2)
    for i, (bw, c) in enumerate([(3, BLUE), (2, PURPLE), (3, PINK), (2, GREEN)]):
        bx = sx + 2 + i * 4
        P(bx, Y(sy - 6), c, bw, 6)
        P(bx, Y(sy - 6), BG, bw, 1)
    P(sx + 20, Y(sy - 3), YELLOW, 3, 3)  # duck
    P(sx + 21, Y(sy - 4), YELLOW, 1, 1)  # head
    P(sx + 23, Y(sy - 3), ORANGE)        # beak

    # --- desk ---
    dx, dy, dw = 6, 40, 114
    P(dx, Y(dy), DESK, dw, 3)
    P(dx, Y(dy + 3), DESK_DK, dw, 1)
    P(dx + 2, Y(dy + 4), DESK_DK, 2, 6)
    P(dx + dw - 4, Y(dy + 4), DESK_DK, 2, 6)

    # --- oscilloscope (left on desk) ---
    ox, oyy = 10, 30
    P(ox, Y(oyy), FRAME, 14, 10)
    P(ox + 1, Y(oyy + 1), "#081018", 12, 6)
    sine(ox + 2, ox + 12, Y(oyy + 4), GREEN, amp=2, period=6)
    P(ox + 2, Y(oyy + 8), STEEL, 2, 1)
    P(ox + 5, Y(oyy + 8), ORANGE, 2, 1)
    P(ox + 8, Y(oyy + 8), STEEL, 1, 1)

    # --- two laptops = stereo rig ---
    for lx, wave_col in [(30, BLUE), (46, PINK)]:
        P(lx, Y(30), FRAME, 12, 9)          # lid
        P(lx + 1, Y(31), SCREEN, 10, 7)     # screen
        sine(lx + 2, lx + 10, Y(34), wave_col, amp=2, period=5)
        P(lx - 1, Y(39), STEEL, 14, 1)      # base

    # --- character in hoodie at the desk ---
    cx = 60
    P(cx + 2, Y(24), HAIR, 5, 3)          # hair
    P(cx + 2, Y(27), SKIN, 5, 2)          # face
    P(cx + 6, Y(28), HAIR)                # eye hint
    P(cx + 1, Y(29), HOOD, 7, 2)          # hood/shoulders
    P(cx, Y(31), HOOD, 9, 8)              # torso
    P(cx - 2, Y(32), HOOD_DK, 2, 2)       # arm reaching laptop
    P(cx + 9, Y(32), HOOD_DK, 2, 2)
    P(cx, Y(39), PANTS, 9, 2)
    # chair
    P(cx - 1, Y(41), FRAME, 11, 1)
    P(cx + 9, Y(32), FRAME, 2, 9)         # backrest
    P(cx + 1, Y(42), FRAME, 2, 5)
    P(cx + 6, Y(42), FRAME, 2, 5)

    # --- mug with steam ---
    P(86, Y(36), YELLOW, 3, 4)
    P(89, Y(37), YELLOW, 1, 2)
    P(86, Y(36), BG, 3, 1)
    P(87, Y(33), STEEL)
    P(88, Y(32), STEEL)

    # --- phone on tripod ---
    tx = 92
    P(tx, Y(26), BG, 6, 10)               # phone body
    P(tx + 1, Y(27), "#0E2036", 4, 8)     # screen glow
    P(tx + 2, Y(28), BLUE)                # capture dot
    P(tx + 2, Y(36), FRAME, 2, 3)         # mount
    P(tx - 2, Y(39), FRAME, 1, 5)         # tripod legs
    P(tx + 6, Y(39), FRAME, 1, 5)
    P(tx + 2, Y(40), FRAME, 1, 6)

    # --- EEG headset on stand ---
    hx = 108
    P(hx + 4, Y(30), FRAME, 1, 10)        # stand pole
    P(hx + 1, Y(40), FRAME, 7, 1)         # base
    P(hx, Y(24), PINK, 9, 2)              # headband
    P(hx - 1, Y(25), PINK, 1, 2)
    P(hx + 9, Y(25), PINK, 1, 2)
    for i in range(3):
        P(hx + 1 + i * 3, Y(26), PURPLE)  # electrodes

    # --- cables ---
    for gx in range(29, 10, -1):
        P(gx, Y(41 if gx % 3 else 42), TEXT_DIM)


def render(path):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * S}" height="{H * S}" viewBox="0 0 {W * S} {H * S}" shape-rendering="crispEdges">',
        f'<rect width="{W * S}" height="{H * S}" fill="{BG}"/>',
    ]
    # grid dots on name band
    for gy in range(1, NAME_H - 2, 2):
        for gx in range(1, W, 2):
            parts.append(f'<rect x="{gx * S}" y="{gy * S}" width="2" height="2" fill="{GRID}"/>')
    for gx, gy, c, w, h in px:
        parts.append(f'<rect x="{gx * S}" y="{gy * S}" width="{w * S}" height="{h * S}" fill="{c}"/>')
    parts.append("</svg>\n")
    with open(path, "w") as f:
        f.write("\n".join(parts))


def ascii_preview():
    grid = {}
    for gx, gy, c, w, h in px:
        for dy in range(h):
            for dx in range(w):
                grid[(gx, gy + dy)] = c
    color2ch = {c: ch for ch, c in [
        (".", BG), (" ", WALL), (",", WALL_DK), ("-", FLOOR), ("=", FLOOR_LN),
        (":", GRID), ("#", FRAME), ("T", DESK), ("t", DESK_DK), ("s", SCREEN),
        ("B", BLUE), ("P", PURPLE), ("F", PINK), ("G", GREEN), ("Y", YELLOW),
        ("O", ORANGE), ("c", CREAM), ("f", SKIN), ("h", HAIR), ("H", HOOD),
        ("d", HOOD_DK), ("p", PANTS), ("|", STEEL), ("_", TEXT_DIM),
        ("w", "#0A1122"), ("q", "#0D1830"), ("a", "#12182A"), ("g", "#081018"),
        ("e", "#0E2036"), ("y", "#4A3B12"),
    ]}

    def pick(c):
        ch = color2ch.get(c)
        if ch:
            return ch
        r = int(c[1:3], 16)
        return "N" if r > 100 else "?"  # N = name-letter gradient

    out = []
    for gy in range(H):
        row = "".join(pick(grid.get((gx, gy), BG)) for gx in range(W))
        out.append(row)
    print("\n".join(out))


# ---------- chapter mini-banners ----------
# each builder receives a plot fn P(x, y, color, w=1, h=1) on its own grid

def _sine_px(P, x0, x1, y_mid, color, amp=2, period=6, phase=0):
    import math
    prev = None
    for gx in range(x0, x1):
        yy = y_mid + round(amp * math.sin((gx + phase) * 2 * math.pi / period))
        if prev is not None and abs(yy - prev) > 1:
            for k in range(min(yy, prev), max(yy, prev) + 1):
                P(gx - 1, k, color)
        P(gx, yy, color)
        prev = yy


def build_ship(P):  # 126 x 12 — merged medals + shipping rocket
    P(2, 9, FRAME, 122, 1)                      # shelf
    P(4, 10, FRAME, 2, 2)
    P(120, 10, FRAME, 2, 2)
    # git-merge glyph, left
    P(6, 2, PURPLE, 2, 2)
    P(6, 4, STEEL, 1, 3)
    P(6, 7, STEEL, 8, 1)
    P(14, 6, GREEN, 2, 2)
    P(13, 7, GREEN)
    P(22, 4, STEEL, 1, 3)
    P(22, 4, STEEL, 6, 1)
    P(28, 3, PINK, 2, 2)
    # six merged medals
    for i in range(6):
        mx = 40 + i * 9
        P(mx + 1, 4, PINK, 1, 2)                # ribbon
        P(mx, 6, YELLOW, 3, 3)                  # medal
        P(mx + 1, 7, ORANGE)                    # core
    # rocket, right
    P(112, 3, CREAM, 4, 6)                      # body
    P(112, 2, PINK, 4, 1)                       # nose
    P(113, 5, BLUE)                             # window
    P(111, 7, PINK, 1, 2)                       # fins
    P(116, 7, PINK, 1, 2)
    P(112, 9, ORANGE, 4, 1)                     # flame
    P(113, 10, YELLOW, 2, 1)
    for sx, sy in [(104, 3), (108, 7), (122, 5), (100, 8), (124, 2)]:
        P(sx, sy, CREAM)                        # stars


def build_specimens(P):  # 126 x 14 — five artifact cases on a shelf
    P(2, 12, FRAME, 122, 2)
    names = [BLUE, PINK, PURPLE, GREEN, YELLOW]
    for i in range(5):
        cx = 8 + i * 24
        P(cx, 2, FRAME, 18, 10)                 # case
        P(cx + 1, 3, "#101826", 16, 7)          # glass
        P(cx + 3, 11, names[i], 12, 1)          # label strip
    # 1: EEG brain — pink blob + squiggle
    P(12, 5, PINK, 6, 4)
    P(11, 6, PINK, 8, 2)
    P(13, 6, "#101826")
    P(15, 7, "#101826")
    _sine_px(P, 18, 24, 6, PINK, amp=2, period=4)
    # 2: stick figure — motion capture
    fx = 34
    P(fx + 3, 4, SKIN, 2, 2)
    P(fx + 4, 6, CREAM, 1, 3)
    P(fx + 2, 7, CREAM, 5, 1)
    P(fx + 2, 9, CREAM, 1, 1)
    P(fx + 6, 9, CREAM, 1, 1)
    P(fx + 1, 10, BLUE, 1, 1)
    P(fx + 7, 10, PINK, 1, 1)
    # 3: OMR sheet — projX
    ox = 58
    P(ox, 4, CREAM, 9, 6)
    for r in range(3):
        for c in range(4):
            P(ox + 1 + c * 2, 5 + r * 2, PURPLE if (r + c) % 3 == 0 else BG)
    # 4: terminal
    tx = 82
    P(tx, 4, BG, 10, 6)
    P(tx, 4, FRAME, 10, 1)
    P(tx + 1, 6, GREEN, 1, 1)
    P(tx + 3, 6, GREEN, 4, 1)
    P(tx + 1, 8, STEEL, 5, 1)
    # 5: tic-tac-toe grid
    gx0 = 104
    P(gx0 + 1, 4, STEEL, 5, 1)
    P(gx0 + 1, 8, STEEL, 5, 1)
    P(gx0 + 2, 4, STEEL, 1, 6)
    P(gx0 + 5, 4, STEEL, 1, 6)
    P(gx0 + 2, 4, PINK)            # X marks
    P(gx0 + 4, 6, PINK)
    P(gx0 + 6, 8, PINK)
    P(gx0 + 5, 4, BLUE, 1, 1)
    P(gx0 + 2, 8, BLUE, 1, 1)


def build_calibrate(P):  # 126 x 10 — ruler, spirit level, tuning fork
    P(6, 4, DESK, 64, 3)                        # ruler body
    P(6, 4, DESK_DK, 64, 1)
    for i in range(0, 64, 4):                   # ticks
        P(8 + i, 4, CREAM, 1, 2 if i % 8 == 0 else 1)
    P(70, 4, ORANGE, 2, 3)                      # ruler end cap
    # spirit level
    P(84, 3, FRAME, 20, 4)
    P(85, 4, "#0E3A2A", 18, 2)
    P(92, 4, "#7CE8C8", 3, 2)                   # bubble
    P(86, 7, STEEL, 16, 1)
    # tuning fork
    P(115, 1, STEEL, 1, 4)
    P(120, 1, STEEL, 1, 4)
    P(115, 5, STEEL, 6, 1)
    P(117, 6, STEEL, 2, 3)
    _sine_px(P, 106, 114, 2, PURPLE, amp=2, period=5)  # resonance waves
    P(122, 2, PURPLE)
    P(124, 4, PURPLE)


def build_bench(P):  # 126 x 10 — instrument rack panel
    P(2, 1, FRAME, 122, 8)
    P(3, 2, "#12182A", 120, 6)
    P(4, 2, STEEL)
    P(121, 2, STEEL)
    # voltmeter with needle
    P(8, 3, "#081018", 18, 5)
    for i in range(5):
        P(10 + i * 3, 3, CREAM)                 # scale ticks
    for i in range(4):                          # needle
        P(13 + i, 7 - i, GREEN)
    P(16, 7, STEEL, 2, 1)
    # two dials
    for dx_ in (34, 46):
        P(dx_, 3, "#1B2230", 6, 5)
        P(dx_ + 2, 4, ORANGE, 1, 2)
        P(dx_ + 5, 3, STEEL)
    # toggle switches
    for i, up in enumerate([True, False, True]):
        sx = 62 + i * 6
        P(sx, 6, STEEL, 4, 1)
        P(sx + 1, 4 if up else 5, YELLOW, 2, 2 if up else 1)
    # LED row
    for i, c in enumerate([GREEN, GREEN, YELLOW, BLUE, PINK]):
        P(88 + i * 4, 3, c)
    # patch cables
    P(84, 7, BLUE, 14, 1)
    P(98, 6, PINK, 10, 1)
    P(108, 7, GREEN, 12, 1)


def build_ground(P):  # 126 x 12 — radio tower with signal waves
    # lattice tower
    for r in range(10):
        P(63 - r, r + 1, STEEL)
        P(63 + r, r + 1, STEEL)
        if r % 2 == 0 and r > 0:
            P(63 - r + 1, r + 1, TEXT_DIM, 2 * r - 1, 1)
    P(63, 0, PINK)                              # beacon
    P(52, 11, FRAME, 24, 1)                     # base
    # signal arcs, both sides
    for side in (-1, 1):
        for k, (ax, y0, y1) in enumerate([(78, 4, 8), (83, 2, 10), (88, 0, 12)]):
            x = 63 + side * (16 + k * 5)
            for yy in range(y0, y1 + 1, 2):
                P(x, yy, PURPLE)
    # receiving dish, left
    P(18, 5, BLUE, 6, 2)
    P(20, 7, BLUE, 2, 1)
    P(20, 8, STEEL, 1, 3)
    P(18, 11, FRAME, 5, 1)
    # globe, right
    P(102, 5, "#123A5C", 8, 6)
    P(103, 4, "#123A5C", 6, 1)
    P(103, 11, "#123A5C", 6, 1)
    P(105, 4, STEEL, 1, 8)
    P(102, 7, CREAM, 8, 1)
    P(98, 12, GREEN, 3, 1)                      # ground scrub
    P(112, 12, GREEN, 2, 1)


def _render_named(path, w, h, blocks, dots=False):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * S}" height="{h * S}" viewBox="0 0 {w * S} {h * S}" shape-rendering="crispEdges">',
        f'<rect width="{w * S}" height="{h * S}" fill="{BG}"/>',
    ]
    if dots:
        for gy in range(1, h, 2):
            for gx in range(1, w, 2):
                parts.append(f'<rect x="{gx * S}" y="{gy * S}" width="2" height="2" fill="{GRID}"/>')
    for gx, gy, c, bwr, bhr in blocks:
        parts.append(f'<rect x="{gx * S}" y="{gy * S}" width="{bwr * S}" height="{bhr * S}" fill="{c}"/>')
    parts.append("</svg>\n")
    with open(path, "w") as f:
        f.write("\n".join(parts))


def _ascii_blocks(w, h, blocks):
    grid = {}
    for gx, gy, c, bwr, bhr in blocks:
        for dy in range(bhr):
            for dx in range(bwr):
                grid[(gx, gy + dy)] = c
    for gy in range(h):
        print("".join({"#0D1117": "."}.get(grid.get((gx, gy), BG), "X") if False else ("#" if grid.get((gx, gy)) else ".") for gx in range(w)))


def make_section(name):
    builders = {"ship": build_ship, "specimens": build_specimens,
                "calibrate": build_calibrate, "bench": build_bench, "ground": build_ground}
    sizes = {"ship": (126, 12), "specimens": (126, 14), "calibrate": (126, 10),
             "bench": (126, 10), "ground": (126, 12)}
    w, h = sizes[name]
    blocks = []
    builders[name](lambda x, y, c, bwr=1, bhr=1: blocks.append((x, y, c, bwr, bhr)))
    return w, h, blocks


if __name__ == "__main__":
    import os
    here = os.path.dirname(__file__)
    out_dir = os.path.join(here, "..", "assets")

    if "--section" in sys.argv:
        name = sys.argv[sys.argv.index("--section") + 1]
        w, h, blocks = make_section(name)
        if "--ascii" in sys.argv:
            for gy in range(h):
                rowmap = {}
                for gx, gy2, c, bwr, bhr in blocks:
                    if gy2 <= gy < gy2 + bhr:
                        for dx in range(bwr):
                            rowmap[(gx + dx, gy)] = c
                print("".join({BG: "."}.get(rowmap.get((gx, gy), BG), "#") for gx in range(w)))
        else:
            p = os.path.join(out_dir, f"pixel-{name}.svg")
            _render_named(p, w, h, blocks)
            print(f"wrote {p} ({len(blocks)} blocks)")
    else:
        draw_name(1)
        draw_scene(NAME_H)
        if "--ascii" in sys.argv:
            ascii_preview()
        else:
            out = os.path.join(out_dir, "pixel-hero.svg")
            render(out)
            print(f"wrote {out} ({len(px)} blocks)")
        for nm in ["ship", "specimens", "calibrate", "bench", "ground"]:
            w, h, blocks = make_section(nm)
            p = os.path.join(out_dir, f"pixel-{nm}.svg")
            _render_named(p, w, h, blocks)
            print(f"wrote {p} ({len(blocks)} blocks)")
