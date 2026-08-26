from pathlib import Path
from PIL import Image, ImageOps

def convert_image(source: Path, output: Path, fmt: str):
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        if fmt == "JPEG":
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, "white")
                alpha = img.convert("RGBA")
                bg.paste(alpha, mask=alpha.getchannel("A"))
                img = bg
            else:
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=92, optimize=True, progressive=True)
        else:
            img.save(output, format="PNG", optimize=True)
