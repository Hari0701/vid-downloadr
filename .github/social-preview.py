"""Render the GitHub social preview card (1280x640) in the app's palette."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 640
SURFACE = (7, 8, 12)
ACCENT = (99, 102, 241)
FUCHSIA = (217, 70, 239)
MUTED = (139, 147, 167)

SF = "/System/Library/Fonts/SFNS.ttf"


def font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    """SF is a variable font; select a named instance.

    Do not use set_variation_by_axes here — axis 0 is Width, not Weight, so a
    weight value there stretches the glyphs instead of thickening them.
    """
    f = ImageFont.truetype(SF, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def glow(canvas: Image.Image, cx: int, cy: int, radius: int, colour, strength: float) -> None:
    """Soft radial wash, matching the .aurora background in globals.css."""
    layer = Image.new("RGB", (W, H), SURFACE)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius), fill=int(255 * strength)
    )
    mask = mask.filter(ImageFilter.GaussianBlur(radius // 2))
    ImageDraw.Draw(layer).rectangle((0, 0, W, H), fill=colour)
    canvas.paste(Image.composite(layer, canvas, mask), (0, 0))


img = Image.new("RGB", (W, H), SURFACE)
glow(img, 210, -40, 460, ACCENT, 0.30)
glow(img, 1120, 40, 400, FUCHSIA, 0.20)
glow(img, 640, 600, 420, (56, 189, 248), 0.10)

draw = ImageDraw.Draw(img)

# Faint grid, fading out toward the bottom like the live page.
for x in range(0, W, 64):
    draw.line([(x, 0), (x, H)], fill=(20, 22, 30), width=1)
for y in range(0, H, 64):
    draw.line([(0, y), (W, y)], fill=(20, 22, 30), width=1)

LEFT = 88

# Mark + wordmark.
draw.rounded_rectangle((LEFT, 92, LEFT + 46, 138), radius=12, fill=ACCENT)
draw.text((LEFT + 23, 113), "↓", font=font(26, "Bold"), fill="white", anchor="mm")
draw.text((LEFT + 62, 114), "vid-downloadr", font=font(27, "Semibold"), fill=(230, 232, 242), anchor="lm")

# Headline.
draw.text((LEFT, 210), "Download media", font=font(82, "Bold"), fill=(245, 246, 252))
draw.text((LEFT, 300), "from anywhere", font=font(82, "Bold"), fill=(170, 178, 250))

# Subtitle.
draw.text(
    (LEFT, 412),
    "Self-hostable downloader · FastAPI + Next.js · no account, nothing kept",
    font=font(25),
    fill=MUTED,
)

# Platform chips.
x = LEFT
for label in ["YouTube", "Instagram", "X", "Pinterest", "+1000 via yt-dlp"]:
    chip = font(21)
    w = draw.textlength(label, font=chip)
    draw.rounded_rectangle((x, 480, x + w + 34, 526), radius=23, outline=(45, 51, 70), width=1)
    draw.text((x + 17, 503), label, font=chip, fill=(198, 204, 222), anchor="lm")
    x += w + 34 + 12

# Footer strip.
draw.text((LEFT, 574), "MIT licensed · github.com/Hari0701/vid-downloadr", font=font(20), fill=(96, 103, 122))

img.save("/Users/hariharan/hari/projects/vid-downloadr/.github/social-preview.png", optimize=True)
print("written")
