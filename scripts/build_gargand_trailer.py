#!/usr/bin/env python3
"""Generate Gargand's original 1080p cinematic product trailer without third-party footage."""
from __future__ import annotations

import array
import base64
import io
import math
import os
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
OUT = STATIC / "gargand-trailer.mp4"
TEMP_VIDEO = STATIC / ".gargand-trailer-video.mp4"
TEMP_WAV = STATIC / ".gargand-trailer-audio.wav"
WIDTH, HEIGHT = 1920, 1080
FPS = 24
SCENE_SECONDS = 6
SCENES = 6
DURATION = SCENE_SECONDS * SCENES
CROSSFADE = 1.05

FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ],
}

def font(which: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES[which]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)

FONT_LABEL = font("bold", 18)
FONT_SMALL = font("regular", 19)
FONT_UI = font("regular", 23)
FONT_UI_BOLD = font("bold", 24)
FONT_SUBTITLE = font("regular", 29)
FONT_TITLE = font("bold", 82)
FONT_TITLE_SMALL = font("bold", 72)

def load_logo() -> Image.Image:
    encoded_path = STATIC / "gargand-pfp.jpg.b64"
    try:
        encoded = encoded_path.read_bytes().strip()
        if encoded.startswith(b"data:") and b"," in encoded:
            encoded = encoded.split(b",", 1)[1]
        image = Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))).convert("RGBA")
    except Exception:
        image = Image.open(io.BytesIO((STATIC / "gargand-mark.svg").read_bytes())).convert("RGBA")
    return image

def make_background() -> Image.Image:
    base = Image.new("RGBA", (WIDTH, HEIGHT), (3, 3, 2, 255))
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        f = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=(int(4 + 3 * f), int(4 + 2 * f), int(2 + f), 255))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((840, 30, 1940, 970), fill=(176, 118, 18, 35))
    gd.ellipse((-380, 430, 850, 1500), fill=(116, 77, 13, 28))
    gd.ellipse((500, 280, 1440, 1050), fill=(70, 48, 8, 26))
    glow = glow.filter(ImageFilter.GaussianBlur(170))
    base.alpha_composite(glow)
    return base

BASE = make_background()
LOGO = load_logo()
LOGO.thumbnail((520, 520), Image.Resampling.LANCZOS)
STARS = []
seed = 9364
for i in range(190):
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    x = seed % WIDTH
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    y = seed % HEIGHT
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    speed = 2 + seed % 15
    STARS.append((x, y, speed, i % 5, 1 if i % 4 else 2))

SCENE_COPY = [
    ("01 / A NEW GUARDIAN RISES", ["YOUR SERVER.", "YOUR REALM."], "Meet Gargand: a golden guardian for the moving parts of your Discord community."),
    ("02 / LAYERED PROTECTION", ["SECURITY.", "WITH PURPOSE."], "Keep supported safeguards and configurable protection tools close to your staff."),
    ("03 / MODERATION, MADE CLEAR", ["TAKE ACTION.", "KEEP CONTEXT."], "Bring common staff actions into one workflow with clearer context and logs."),
    ("04 / THE COMMUNITY EXPERIENCE", ["MAKE ROOM", "FOR PEOPLE."], "Tickets, verification, roles and community tools help members find their way."),
    ("05 / YOUR WEB CONTROL ROOM", ["ONE PLACE.", "MORE CONTROL."], "Choose your server and manage supported settings from the Gargand website."),
    ("06 / YOUR NEXT CHAPTER", ["COMMAND THE", "CHAOS."], "Invite Gargand, explore its commands, and bring order to your community."),
]

GOLD = (255, 211, 77, 255)
PALE = (255, 246, 221, 255)
MUTED = (201, 184, 145, 255)
DARK = (8, 7, 4, 242)
LINE = (207, 161, 48, 170)

def rounded(draw: ImageDraw.ImageDraw, box, radius=20, fill=DARK, outline=LINE, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def draw_text(draw: ImageDraw.ImageDraw, xy, value: str, fnt, fill=PALE, stroke=0):
    draw.text(xy, value, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 240))

def draw_wrap(draw, text, x, y, max_width, fnt, fill=MUTED, line_gap=12, max_lines=3):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for index, line in enumerate(lines[:max_lines]):
        draw_text(draw, (x, y + index * (fnt.size + line_gap)), line, fnt, fill)

def draw_header(draw, t, scene_index):
    draw_text(draw, (92, 60), "GARGAND", FONT_LABEL, GOLD)
    draw_text(draw, (224, 60), "// CINEMATIC PRODUCT FILM", FONT_SMALL, MUTED)
    right = "MODERATION  /  SECURITY  /  COMMUNITY"
    box = draw.textbbox((0, 0), right, font=FONT_SMALL)
    draw_text(draw, (WIDTH - 92 - (box[2] - box[0]), 60), right, FONT_SMALL, MUTED)
    draw.line((92, 101, WIDTH - 92, 101), fill=(189, 145, 37, 90), width=1)
    # Film letterbox and a finely lit golden progress rail.
    draw.rectangle((0, 0, WIDTH, 26), fill=(0, 0, 0, 255))
    draw.rectangle((0, HEIGHT - 32, WIDTH, HEIGHT), fill=(0, 0, 0, 255))
    draw.rectangle((92, HEIGHT - 18, WIDTH - 92, HEIGHT - 15), fill=(65, 49, 18, 180))
    progress = min(1.0, max(0.0, t / DURATION))
    draw.rectangle((92, HEIGHT - 18, int(92 + (WIDTH - 184) * progress), HEIGHT - 15), fill=GOLD)
    draw_text(draw, (92, HEIGHT - 66), "GARGAND  ·  COMMAND THE CHAOS", FONT_SMALL, (166, 148, 107, 255))
    timecode = f"{int(t // 60):02d}:{int(t % 60):02d}  /  00:{DURATION:02d}"
    bb = draw.textbbox((0, 0), timecode, font=FONT_SMALL)
    draw_text(draw, (WIDTH - 92 - (bb[2]-bb[0]), HEIGHT - 66), timecode, FONT_SMALL, (166, 148, 107, 255))

def draw_stars(frame: Image.Image, t):
    draw = ImageDraw.Draw(frame, "RGBA")
    for x, y, speed, phase, radius in STARS:
        px = int((x + t * speed * 2.8) % WIDTH)
        py = int((y + t * (speed * 0.42)) % HEIGHT)
        pulse = 0.45 + 0.55 * abs(math.sin(t * 0.7 + phase))
        alpha = int((80 + 130 * pulse) if radius == 1 else (100 + 130 * pulse))
        draw.ellipse((px, py, px + radius, py + radius), fill=(255, 225, 147, min(230, alpha)))
    # Slowly traveling angled light shaft, restrained against the dark palette.
    x = int((t * 42) % (WIDTH + 900)) - 900
    draw.polygon([(x, 118), (x + 130, 118), (x + 670, HEIGHT - 100), (x + 550, HEIGHT - 100)],
                 fill=(255, 205, 77, 7))

def draw_lion(frame: Image.Image, t, center=(1450, 525), size=430):
    draw = ImageDraw.Draw(frame, "RGBA")
    cx, cy = center
    radius = int(size * (0.52 + 0.008 * math.sin(t * 0.8)))
    for r, alpha in [(radius + 68, 22), (radius + 34, 29), (radius + 10, 38)]:
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(255, 204, 65, alpha), width=2)
    angle = t * 0.19
    for i in range(12):
        a = angle + i * math.tau / 12
        ox = int(cx + math.cos(a) * (radius + 25))
        oy = int(cy + math.sin(a) * (radius + 25))
        draw.ellipse((ox-3, oy-3, ox+3, oy+3), fill=GOLD)
    # Clip the source artwork to a high-quality circular alpha mask so no square
    # corners from its JPG background can appear in the finished film.
    logo = LOGO.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask_big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask_big).ellipse((2, 2, size * 4 - 3, size * 4 - 3), fill=255)
    circle_mask = mask_big.resize((size, size), Image.Resampling.LANCZOS)
    logo.putalpha(ImageChops.multiply(logo.getchannel("A"), circle_mask))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((size * .04, size * .04, size * .96, size * .96), fill=(255, 193, 37, 36))
    glow = glow.filter(ImageFilter.GaussianBlur(max(8, size // 13)))
    frame.alpha_composite(glow, (cx - size // 2, cy - size // 2))
    frame.alpha_composite(logo, (cx - size // 2, cy - size // 2))
    draw = ImageDraw.Draw(frame, "RGBA")
    edge = size // 2 - 2
    draw.ellipse((cx-edge, cy-edge, cx+edge, cy+edge), outline=(255, 221, 118, 182), width=2)

def draw_title(frame: Image.Image, scene_index, local_t):
    draw = ImageDraw.Draw(frame, "RGBA")
    kicker, lines, subtitle = SCENE_COPY[scene_index]
    reveal = min(1.0, max(0.0, local_t / 1.0))
    offset = int(58 * (1 - reveal))
    draw_text(draw, (104 + offset, 245), kicker, FONT_LABEL, GOLD)
    title_font = FONT_TITLE_SMALL if scene_index == 5 else FONT_TITLE
    y = 325
    for i, line in enumerate(lines):
        color = PALE if i == 0 else GOLD
        # Last title has a shorter line; it remains cinematic instead of shrinking to fit.
        if scene_index == 5:
            title_font = FONT_TITLE_SMALL
        draw_text(draw, (98 + offset, y + i * 104), line, title_font, color, stroke=1)
    draw_wrap(draw, subtitle, 104 + offset, y + len(lines) * 104 + 24, 680, FONT_SUBTITLE, MUTED, 14, 3)
    draw.line((104, 750, 410, 750), fill=(255, 211, 77, 180), width=2)
    draw_text(draw, (104, 774), "GARGAND  ·  BUILT FOR COMMUNITIES", FONT_SMALL, (159, 142, 99, 255))

def draw_security_visual(frame, t):
    draw = ImageDraw.Draw(frame, "RGBA")
    cx, cy = 1445, 470
    pulse = 6 * math.sin(t * 1.8)
    for r, c in [(270, (211, 165, 49, 45)), (220, (255, 213, 77, 85)), (165, (211, 165, 49, 52))]:
        rr = int(r + pulse)
        draw.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), outline=c, width=2)
    points = [(cx,cy-155),(cx+125,cy-102),(cx+108,cy+55),(cx,cy+155),(cx-108,cy+55),(cx-125,cy-102)]
    draw.polygon(points, fill=(15, 11, 4, 245), outline=GOLD)
    for i in range(2):
        inset = 24 + i*19
        pts = [(cx,cy-155+inset),(cx+125-inset//2,cy-102+inset//3),(cx+108-inset//2,cy+55-inset//3),(cx,cy+155-inset),(cx-108+inset//2,cy+55-inset//3),(cx-125+inset//2,cy-102+inset//3)]
        draw.line(pts + [pts[0]], fill=(211,165,49,170-i*50), width=2, joint="curve")
    draw_text(draw, (cx-26, cy-40), "G", font("bold", 112), GOLD)
    rounded(draw, (1070, 690, 1810, 858), 19, fill=(7,6,3,245), outline=(204,158,42,160))
    draw_text(draw, (1105, 714), "GARGAND / SECURITY STATUS", FONT_SMALL, MUTED)
    rows = [("Anti-raid watch", "READY"), ("Protection rules", "CONFIGURED"), ("Staff log trail", "TRACEABLE")]
    for j, (label, state) in enumerate(rows):
        yy = 755 + j*32
        draw.line((1105, yy-4, 1775, yy-4), fill=(255,255,255,24), width=1)
        draw_text(draw, (1110, yy), label, FONT_SMALL, PALE)
        draw_text(draw, (1648, yy), state, FONT_LABEL, GOLD)

def draw_moderation_visual(frame, t):
    draw = ImageDraw.Draw(frame, "RGBA")
    box = (1040, 255, 1810, 825)
    rounded(draw, box, 20, fill=(7,6,3,246), outline=(205,161,48,190))
    draw.rounded_rectangle((1040,255,1810,323), radius=20, fill=(22,16,6,255), outline=(205,161,48,145), width=1)
    draw.rectangle((1040,295,1810,323), fill=(22,16,6,255))
    for i, col in enumerate([(255,206,73,255),(167,125,36,255),(104,78,24,255)]):
        draw.ellipse((1072+i*22,280,1084+i*22,292), fill=col)
    draw_text(draw, (1170, 278), "GARGAND / MODERATION CONSOLE", FONT_SMALL, MUTED)
    rows = [
        ("!", "!warn @member", "Record a warning for review", "LOGGED"),
        ("◷", "!timeout @member", "Apply a staff-selected duration", "STAFF"),
        ("#", "!lock", "Control access to a channel", "READY"),
        ("⌕", "Staff audit trail", "Review supported staff actions", "TRACE"),
    ]
    for i, (icon, cmd, desc, state) in enumerate(rows):
        yy = 350 + i*112
        if i % 2 == 0:
            draw.rounded_rectangle((1065, yy-7, 1785, yy+94), radius=10, fill=(255,255,255,8))
        draw.rounded_rectangle((1082, yy+9, 1132, yy+59), radius=10, fill=(255,211,77,20), outline=(255,211,77,85), width=1)
        draw_text(draw, (1098, yy+15), icon, FONT_UI_BOLD, GOLD)
        draw_text(draw, (1153, yy+3), cmd, FONT_UI_BOLD, PALE)
        draw_text(draw, (1153, yy+42), desc, FONT_SMALL, MUTED)
        draw_text(draw, (1640, yy+59), state, font("bold", 15), GOLD)

def draw_community_visual(frame, t):
    draw = ImageDraw.Draw(frame, "RGBA")
    cx, cy = 1440, 480
    for r in (130, 180, 235):
        draw.ellipse((cx-r,cy-r,cx+r,cy+r), outline=(223,174,48,65), width=2)
    for i, color in enumerate([(255,218,111,255),(189,143,54,255),(226,183,116,255),(140,164,90,255)]):
        a = t*0.15 + i*math.tau/4
        x = int(cx + math.cos(a)*225)
        y = int(cy + math.sin(a)*225)
        draw.ellipse((x-28,y-28,x+28,y+28), fill=(8,7,4,255), outline=color, width=4)
        draw.ellipse((x-14,y-14,x+14,y+14), fill=color)
    rounded(draw, (1120, 300, 1780, 680), 22, fill=(7,6,3,246), outline=(205,161,48,180))
    draw_text(draw, (1160, 337), "SUPPORT TICKET  #204", FONT_SMALL, MUTED)
    draw_text(draw, (1160, 388), "A member needs a hand.", FONT_UI_BOLD, PALE)
    draw_wrap(draw, "“Hey! I need help getting set up in the server.”", 1160, 446, 550, FONT_UI, MUTED, 11, 3)
    draw.line((1160, 556, 1735, 556), fill=(255,255,255,35), width=1)
    draw.ellipse((1162, 584, 1180, 602), fill=(129,207,135,255))
    draw_text(draw, (1198, 580), "SUPPORT TEAM", FONT_LABEL, GOLD)
    draw_text(draw, (1198, 612), "Ready to help", FONT_SMALL, MUTED)

def draw_dashboard_visual(frame, t):
    draw = ImageDraw.Draw(frame, "RGBA")
    rounded(draw, (1020, 255, 1825, 815), 20, fill=(6,5,3,250), outline=(205,161,48,190))
    draw.rounded_rectangle((1020,255,1825,322), radius=20, fill=(20,15,6,255), outline=(205,161,48,140), width=1)
    draw.rectangle((1020,293,1825,322), fill=(20,15,6,255))
    draw_text(draw, (1060, 278), "GARGAND", FONT_LABEL, GOLD)
    draw_text(draw, (1190, 280), "SERVER CONTROL ROOM", FONT_SMALL, MUTED)
    draw_text(draw, (1668, 280), "● CONNECTED", font("bold", 15), (157,218,152,255))
    draw.rectangle((1020,323,1210,815), fill=(12,9,4,255))
    for i, label in enumerate(["Overview","Security","Music","Notifications","Settings"]):
        yy = 365 + i*62
        if i == 0:
            draw.rounded_rectangle((1040,yy-8,1190,yy+35),radius=8,fill=(255,211,77,24))
        draw_text(draw,(1054,yy),label,FONT_SMALL,GOLD if i==0 else MUTED)
    stats = [("PROTECTION","01"),("CONTROL","WEB"),("TOOLS","24/7")]
    for i,(label,value) in enumerate(stats):
        x=1240+i*177
        rounded(draw,(x,355,x+158,460),11,fill=(255,255,255,8),outline=(255,255,255,28),width=1)
        draw_text(draw,(x+13,372),label,font("bold",14),MUTED)
        draw_text(draw,(x+13,402),value,font("bold",40),GOLD)
    rounded(draw,(1240,484,1788,777),12,fill=(255,255,255,5),outline=(255,255,255,28),width=1)
    draw_text(draw,(1265,507),"COMMUNITY ACTIVITY",FONT_SMALL,MUTED)
    bar_heights=[63,93,78,126,102,160,119,190,145,175,156,210]
    base_y=738
    for i,height in enumerate(bar_heights):
        animated=height + int(8*math.sin(t*1.5+i*.65))
        x=1270+i*40
        draw.rounded_rectangle((x,base_y-animated,x+22,base_y),radius=5,fill=(233,182,49,230 if i==11 else 155))
    draw.line((1260,739,1765,739),fill=(255,255,255,25),width=1)

def draw_ambient_stars(frame: Image.Image, t: float, duration: float = DURATION):
    """Stars and glow that loop with the same deep-black/gold palette as the site."""
    draw = ImageDraw.Draw(frame, "RGBA")
    phase = (t / max(.001, duration)) * math.tau
    for x, y, speed, phase_index, radius in STARS:
        # Static star positions prevent a jump at a looping boundary; only their
        # luminance breathes, using a whole-cycle phase.
        pulse = 0.48 + 0.42 * math.sin(phase + phase_index * .7 + speed)
        alpha = max(32, min(145, int(65 + 70 * pulse)))
        draw.ellipse((x, y, x+radius, y+radius), fill=(255, 226, 157, alpha))
    # A soft reflection moves across the scene and returns to its initial position.
    shift = math.sin(phase) * 250
    x = int(WIDTH * .55 + shift)
    draw.polygon([(x-90, 100), (x+10, 100), (x+620, HEIGHT-80), (x+510, HEIGHT-80)],
                 fill=(255, 206, 75, 5))

def draw_abstract_shield(frame: Image.Image, t: float, cx=1460, cy=495):
    draw = ImageDraw.Draw(frame, "RGBA")
    phase = (t / 6.0) * math.tau
    for n, alpha in [(270, 24), (225, 30), (176, 37)]:
        radius = int(n + 6 * math.sin(phase))
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                     outline=(255, 204, 65, alpha), width=2)
    points = [(cx,cy-160),(cx+130,cy-105),(cx+112,cy+58),(cx,cy+161),(cx-112,cy+58),(cx-130,cy-105)]
    draw.polygon(points, fill=(15,11,4,120), outline=(255,211,77,125))
    inset_points=[]
    for x,y in points:
        inset_points.append((cx+(x-cx)*.79, cy+(y-cy)*.79))
    draw.line(inset_points+[inset_points[0]], fill=(255,211,77,65), width=2, joint="curve")
    draw.arc((cx-90,cy-90,cx+90,cy+90), 205, 335, fill=(255,232,159,190), width=4)
    draw.line((cx-40,cy+3,cx-8,cy+36,cx+51,cy-37), fill=(255,232,159,225), width=7, joint="curve")

def draw_abstract_commands(frame: Image.Image, t: float):
    draw = ImageDraw.Draw(frame, "RGBA")
    phase = (t / 6.0) * math.tau
    x0,y0,x1,y1 = 1100,235,1800,825
    draw.rounded_rectangle((x0,y0,x1,y1),radius=28,fill=(8,7,4,135),outline=(218,172,56,75),width=2)
    draw.rounded_rectangle((x0,y0,x1,y0+62),radius=27,fill=(42,30,8,90),outline=(218,172,56,50),width=1)
    for i in range(3):
        col=(255,211,77, 90 if i==0 else 45)
        draw.ellipse((x0+28+i*24,y0+25,x0+39+i*24,y0+36),fill=col)
    for row in range(5):
        yy=y0+104+row*90
        draw.rounded_rectangle((x0+28,yy,x1-28,yy+62),radius=12,fill=(255,245,209,7),outline=(255,211,77,24),width=1)
        draw.rounded_rectangle((x0+48,yy+18,x0+64,yy+43),radius=5,fill=(255,211,77,55))
        bar=160+int(28*math.sin(phase+row*.9))
        draw.rounded_rectangle((x0+86,yy+15,x0+86+bar,yy+23),radius=4,fill=(255,226,160,65))
        draw.rounded_rectangle((x0+86,yy+32,x0+330,yy+39),radius=4,fill=(220,190,120,28))
        draw.rounded_rectangle((x1-115,yy+24,x1-53,yy+37),radius=7,outline=(255,211,77,65),width=1)

def draw_abstract_community(frame: Image.Image, t: float):
    draw = ImageDraw.Draw(frame, "RGBA")
    phase=(t/6.0)*math.tau
    cx,cy=1450,495
    for r,alpha in [(150,28),(220,35),(290,20)]:
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(255,207,79,alpha),width=2)
    for i in range(8):
        a=phase*.12+i*math.tau/8
        x=int(cx+math.cos(a)*230); y=int(cy+math.sin(a)*230)
        draw.ellipse((x-23,y-23,x+23,y+23),fill=(8,7,4,140),outline=(255,211,77,100),width=2)
        draw.ellipse((x-8,y-8,x+8,y+8),fill=(255,211,77,85))
        draw.line((cx,cy,x,y),fill=(255,211,77,14),width=1)
    draw.rounded_rectangle((1180,370,1720,650),radius=30,fill=(8,7,4,98),outline=(255,211,77,42),width=2)
    for i in range(4):
        yy=420+i*48
        draw.rounded_rectangle((1220,yy,1260,yy+30),radius=8,fill=(255,211,77,35))
        draw.rounded_rectangle((1285,yy+3,1500+40*(i%2),yy+10),radius=4,fill=(255,240,189,50))
        draw.rounded_rectangle((1285,yy+17,1620,yy+23),radius=4,fill=(255,240,189,24))

def draw_abstract_dashboard(frame: Image.Image, t: float):
    draw = ImageDraw.Draw(frame, "RGBA")
    phase=(t/6.0)*math.tau
    rounded(draw,(1055,245,1810,805),25,fill=(6,5,3,145),outline=(205,161,48,85),width=2)
    draw.rounded_rectangle((1055,245,1810,315),radius=25,fill=(25,18,6,120),outline=(205,161,48,50),width=1)
    draw.rectangle((1055,282,1810,315),fill=(25,18,6,120))
    draw.rounded_rectangle((1085,342,1230,750),radius=14,fill=(255,255,255,5),outline=(255,211,77,20),width=1)
    for i in range(5):
        yy=370+i*68
        draw.rounded_rectangle((1103,yy,1207,yy+23),radius=6,fill=(255,211,77,30 if i==0 else 10))
    for i in range(3):
        x=1255+i*175
        draw.rounded_rectangle((x,342,x+150,445),radius=14,fill=(255,255,255,7),outline=(255,211,77,30),width=1)
        draw.rounded_rectangle((x+15,368,x+80+int(8*math.sin(phase+i)),376),radius=4,fill=(255,221,135,62))
        draw.rounded_rectangle((x+15,393,x+100,420),radius=6,fill=(255,211,77,19))
    draw.rounded_rectangle((1255,465,1780,750),radius=14,fill=(255,255,255,5),outline=(255,211,77,28),width=1)
    base_y=716
    heights=[82,123,99,166,137,202,154,231,181,210,164,225]
    for i,h in enumerate(heights):
        height=h+int(11*math.sin(phase+i*.8))
        x=1280+i*39
        draw.rounded_rectangle((x,base_y-height,x+20,base_y),radius=5,fill=(255,211,77,80+(i%3)*18))

def draw_ambient_scene(scene_index: int, local_t: float, global_t: float, loop_duration: float = DURATION):
    """Background-only scene; the shared website UI supplies all text and controls."""
    frame = BASE.copy()
    draw_ambient_stars(frame, global_t, loop_duration)
    phase = local_t / 6.0
    if scene_index == 0:
        draw_lion(frame, local_t, center=(1500, 495), size=420)
    elif scene_index == 1:
        draw_abstract_shield(frame, local_t)
    elif scene_index == 2:
        draw_abstract_commands(frame, local_t)
    elif scene_index == 3:
        draw_abstract_community(frame, local_t)
    elif scene_index == 4:
        draw_abstract_dashboard(frame, local_t)
    else:
        draw_lion(frame, local_t, center=(1490, 475), size=390)
        draw_abstract_community(frame, local_t)
    draw = ImageDraw.Draw(frame, "RGBA")
    x = int(WIDTH * (.32 + .22 * math.sin(phase*math.tau)))
    draw.ellipse((x-150, HEIGHT+30, x+520, HEIGHT+690), fill=(161,104,14,7))
    return frame

def draw_scene(scene_index, local_t, global_t):
    # Keep all wording in HTML so the film never looks like a separate embed.
    return draw_ambient_scene(scene_index, local_t, global_t)

TAB_SCENES = {
    "home": 0,
    "commands": 2,
    "security": 1,
    "verification": 1,
    "support": 3,
    "announcements": 4,
    "dashboard": 4,
    "community": 3,
}

def build_tab_scenes():
    """Build small, silent, dedicated cinematic loops for the site's main tabs."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    scene_dir = STATIC / "gargand-scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_fps = 15
    scene_duration = 6.0
    scene_frames = int(scene_fps * scene_duration)
    temp_video = scene_dir / ".gargand-scene-temp.mp4"
    try:
        for name, scene_index in TAB_SCENES.items():
            output = scene_dir / f"{name}.mp4"
            writer = imageio_ffmpeg.write_frames(
                str(temp_video), (WIDTH, HEIGHT), fps=scene_fps, codec="libx264",
                pix_fmt_in="rgb24", pix_fmt_out="yuv420p", quality=None,
                macro_block_size=1, ffmpeg_log_level="error",
                output_params=["-crf","27","-preset","veryfast","-movflags","+faststart","-vf","scale=1280:720"],
            )
            writer.send(None)
            try:
                for i in range(scene_frames):
                    t = i / scene_fps
                    frame = draw_ambient_scene(scene_index, t, t, scene_duration)
                    writer.send(frame.convert("RGB").tobytes())
            finally:
                writer.close()
            os.replace(temp_video, output)
            print(f"Created tab ambience {output} ({output.stat().st_size:,} bytes)", flush=True)
    finally:
        try:
            temp_video.unlink()
        except FileNotFoundError:
            pass

def make_audio(path: Path):
    rate = 44100
    total = int(rate * DURATION)
    stereo = array.array("h")
    tau = math.tau
    for n in range(total):
        t = n / rate
        scene_t = t % SCENE_SECONDS
        fade = min(1.0, t / 1.6, max(0.0, (DURATION-t) / 2.4))
        drone = (
            0.12 * math.sin(tau * 55.0 * t) +
            0.065 * math.sin(tau * 82.41 * t + 0.3) +
            0.035 * math.sin(tau * (110.0 + 1.3*math.sin(t*0.4)) * t)
        )
        shimmer = 0.023 * math.sin(tau * 330.0 * t) * math.exp(-scene_t*1.8)
        boom = 0.13 * math.exp(-scene_t*4.2) * math.sin(tau * (48.0 + 9.0*scene_t) * scene_t)
        sample = max(-0.34, min(0.34, (drone + shimmer + boom) * fade))
        left = int(sample * 32767)
        right = int(sample * 32767 * (0.96 + 0.04 * math.sin(t*0.7)))
        stereo.append(left)
        stereo.append(right)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(stereo.tobytes())

def build():
    STATIC.mkdir(parents=True, exist_ok=True)
    audio_available = True
    writer = imageio_ffmpeg.write_frames(
        str(TEMP_VIDEO), (WIDTH, HEIGHT), fps=FPS, codec="libx264",
        pix_fmt_in="rgb24", pix_fmt_out="yuv420p", quality=None,
        macro_block_size=1, ffmpeg_log_level="error",
        output_params=["-crf", "23", "-preset", "veryfast", "-movflags", "+faststart"],
    )
    writer.send(None)
    frame_count = int(DURATION * FPS)
    try:
        for i in range(frame_count):
            t = i / FPS
            index = min(SCENES - 1, int(t // SCENE_SECONDS))
            local = t - index * SCENE_SECONDS
            current = draw_scene(index, local, t)
            if index < SCENES - 1 and local >= SCENE_SECONDS - CROSSFADE:
                next_scene = draw_scene(index + 1, local - (SCENE_SECONDS - CROSSFADE), t)
                amount = min(1.0, (local - (SCENE_SECONDS - CROSSFADE)) / CROSSFADE)
                amount = amount * amount * (3.0 - 2.0 * amount)  # smoothstep cross-dissolve
                frame = Image.blend(current, next_scene, amount)
            else:
                frame = current
            writer.send(frame.convert("RGB").tobytes())
            if i % (FPS * 6) == 0:
                print(f"Rendered frame {i}/{frame_count}", flush=True)
    finally:
        writer.close()

    try:
        make_audio(TEMP_WAV)
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [ffmpeg, "-y", "-i", str(TEMP_VIDEO), "-i", str(TEMP_WAV),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
             "-shortest", "-movflags", "+faststart", str(OUT)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except Exception as exc:
        audio_available = False
        print(f"Audio mux skipped; keeping silent trailer: {exc}", flush=True)
        os.replace(TEMP_VIDEO, OUT)
    finally:
        for tmp in (TEMP_VIDEO, TEMP_WAV):
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
    print(f"Created {OUT} ({OUT.stat().st_size:,} bytes, {WIDTH}x{HEIGHT}, {DURATION}s, audio={audio_available})")
    build_tab_scenes()

if __name__ == "__main__":
    build()
