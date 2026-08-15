"""Pure compression engine — no UI dependencies."""

from __future__ import annotations

import errno
import io
import os
from typing import Callable, Iterable, Optional

from PIL import Image, UnidentifiedImageError

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

HARD_DIM_CAP = 20000
OUTPUT_FOLDER_NAME = "OnlyImg_Output"
SUPPORTED_FORMATS = ("JPEG", "PNG", "WEBP", "BMP")


def generate_image_at_t(
    img: Image.Image, t: float, output_format: str, max_res_limit: int
) -> bytes:
    # Scale from ~0.02x at t=0, to 1.0x at t=50, up to ~46x at t=100 (bounded by HARD_DIM_CAP)
    scale = 10 ** ((t - 50) / 30)

    orig_w, orig_h = img.size
    longest = max(orig_w, orig_h)

    if max_res_limit > 0 and longest * scale > max_res_limit:
        scale = max_res_limit / float(longest)

    new_w = max(1, min(int(orig_w * scale), HARD_DIM_CAP))
    new_h = max(1, min(int(orig_h * scale), HARD_DIM_CAP))

    resized = img.resize((new_w, new_h), RESAMPLE)
    buf = io.BytesIO()

    quality = int(10 + (t / 100.0) * 90)
    quality = max(1, min(quality, 100))

    needs_rgb = output_format in ("JPEG", "BMP")

    if needs_rgb and resized.mode in ("RGBA", "LA"):
        alpha_index = 3 if resized.mode == "RGBA" else 1
        bg = Image.new("RGB", resized.size, (255, 255, 255))
        try:
            bg.paste(resized, mask=resized.split()[alpha_index])
        except Exception:
            bg.paste(resized.convert("RGB"))
        resized = bg
    elif needs_rgb and resized.mode != "RGB":
        resized = resized.convert("RGB")
    elif output_format == "WEBP" and resized.mode == "P":
        resized = resized.convert("RGBA")
    elif output_format == "PNG" and resized.mode == "CMYK":
        resized = resized.convert("RGB")

    if output_format == "JPEG":
        resized.save(buf, format="JPEG", quality=quality, optimize=True)
    elif output_format == "WEBP":
        resized.save(buf, format="WEBP", quality=quality)
    elif output_format == "PNG":
        resized.save(buf, format="PNG", optimize=True)
    else:
        resized.save(buf, format=output_format)

    return buf.getvalue()


def process_single_image(
    img_path: str,
    output_dir: str,
    min_bytes: int,
    max_bytes: int,
    max_res: int,
    out_format: str,
    used_paths: set,
) -> dict:
    orig_kb = 0.0
    try:
        orig_kb = os.path.getsize(img_path) / 1024
    except OSError:
        pass

    base_name = os.path.basename(img_path)
    stem = os.path.splitext(base_name)[0] or "image"
    ext = out_format.lower()

    out_path = os.path.join(output_dir, f"{stem}.{ext}")
    n = 2
    while out_path in used_paths:
        out_path = os.path.join(output_dir, f"{stem}_{n}.{ext}")
        n += 1
    used_paths.add(out_path)

    res = {
        "name": base_name,
        "old_kb": f"{orig_kb:.1f} KB",
        "new_kb": "-",
        "out_path": "",
        "status": "Fail",
        "msg": "",
    }

    try:
        with Image.open(img_path) as img:
            img.load()

            low, high = 0.0, 100.0
            best_data, best_diff = None, float("inf")

            for _ in range(16):
                mid = (low + high) / 2
                data = generate_image_at_t(img, mid, out_format, max_res)
                size = len(data)

                if min_bytes <= size <= max_bytes:
                    best_data = data
                    best_diff = 0
                    break

                diff = (min_bytes - size) if size < min_bytes else (size - max_bytes)
                if diff < best_diff:
                    best_diff = diff
                    best_data = data

                if size < min_bytes:
                    low = mid
                else:
                    high = mid

            if not best_data:
                res["msg"] = "Engine could not produce output for this file."
                return res

            final_size = len(best_data)

            try:
                with open(out_path, "wb") as f:
                    f.write(best_data)
            except PermissionError:
                res["msg"] = "Permission denied writing output file."
                return res
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    res["msg"] = "Disk is full."
                else:
                    res["msg"] = f"Write error: {str(e)[:40]}"
                return res

            res["status"] = "Pass" if min_bytes <= final_size <= max_bytes else "Closest"
            if res["status"] == "Closest":
                res["msg"] = "Closest possible match saved (mathematical boundary fallback)."
            res["new_kb"] = f"{final_size / 1024:.1f} KB"
            res["out_path"] = out_path

    except UnidentifiedImageError:
        res["msg"] = "Unrecognized or corrupt image file."
    except Image.DecompressionBombError:
        res["msg"] = "Image dimensions too large to process safely."
    except MemoryError:
        res["msg"] = "Ran out of memory while processing this file."
    except PermissionError:
        res["msg"] = "Permission denied reading this file."
    except OSError as e:
        res["msg"] = f"I/O error: {str(e)[:40]}"
    except Exception as e:
        res["msg"] = f"Unexpected error: {str(e)[:40]}"

    return res


def collect_valid_images(
    paths: Iterable[str],
    skip_folder_name: str = OUTPUT_FOLDER_NAME,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Walk selected files/folders and return paths that Pillow can verify."""
    all_files: list[str] = []
    for p in paths:
        try:
            if os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if d != skip_folder_name]
                    for f in files:
                        all_files.append(os.path.join(root, f))
            elif os.path.isfile(p):
                all_files.append(p)
        except (PermissionError, OSError):
            continue

    valid: list[str] = []
    total = len(all_files)
    for idx, f in enumerate(all_files, 1):
        try:
            with Image.open(f) as img:
                img.verify()
            valid.append(f)
        except Exception:
            pass
        if on_progress and (idx % 25 == 0 or idx == total):
            on_progress(idx, total)
    return valid
