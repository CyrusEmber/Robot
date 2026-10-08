# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Turn a walking clip into reviewable frame sheets.

Annotating a gait from video needs the pixels in front of a reader, not a player: this fetches a clip
(or takes a local file) and writes a tiled contact sheet, so one image shows a whole window in
row-major order. The sheet's sampling rate, tile shape and scale decide what is actually resolvable,
so they live here rather than in a command pasted into a record -- a run has to be comparable with the
next one.

Nothing is written into the repo: the clip is source material and the sheets are working files, both
under ``--work`` (default: ``%TEMP%/rl_clips`` on Windows).

Tooling (user-level, not repo dependencies):

* ffmpeg -- ``PATH`` first, else the binary bundled with ``imageio_ffmpeg``.
* yt-dlp -- needed for ``--yt-id`` only; ``--video`` skips it.

Usage:

    python rl_exp/tools/diagnose/clip_sheet.py --yt-id S1cZEIqYwx0
    python rl_exp/tools/diagnose/clip_sheet.py --video clip.mp4 --start 9.5 --duration 4 --fps 3
    python rl_exp/tools/diagnose/clip_sheet.py --video clip.mp4 --start 0.3 --duration 2.2 --fps 4 \
        --cols 3 --rows 3 --scale 560 --grid 50
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

_DEFAULT_WORK = pathlib.Path(os.environ.get("TEMP", "/tmp")) / "rl_clips"


def _exe(name: str) -> str:
    """Key each tool exactly once, so both may run from outside ``PATH`` (user-level installs)."""
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
    raise SystemExit(f"{name} not found: install it (user-level is enough) or put it on PATH")


def fetch(yt_id: str, work: pathlib.Path, height: int) -> pathlib.Path:
    """Download ``yt_id`` into ``work`` once. Re-runs reuse the file, so a sheet costs no download."""
    work.mkdir(parents=True, exist_ok=True)
    for hit in sorted(work.glob(f"{yt_id}.*")):
        if hit.suffix in (".mp4", ".mkv", ".webm") and not _is_fragment(hit):
            return hit
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "--ffmpeg-location", _exe("ffmpeg"),
         "-f", f"bv*[height<={height}]+ba/b[height<={height}]", "--merge-output-format", "mp4",
         "-o", str(work / "%(id)s.%(ext)s"), yt_id],
        check=True)
    for hit in sorted(work.glob(f"{yt_id}.mp4")):
        return hit
    raise SystemExit(f"yt-dlp reported success but no merged file for {yt_id} in {work}")


def _is_fragment(path: pathlib.Path) -> bool:
    """Whether ``path`` is a downloaded-but-unmerged fragment, which yt-dlp leaves beside the merge."""
    return path.stem.endswith((".f137", ".f299", ".f251", ".f248", ".f136"))


def sheet(video: pathlib.Path, out: pathlib.Path, start: float, duration: float, fps: float,
          cols: int, rows: int, scale: int) -> pathlib.Path:
    """Write one tiled sheet covering ``[start, start + duration)`` at ``fps`` samples per second."""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(duration),
         "-i", str(video), "-vf", f"fps={fps},scale={scale}:-2,tile={cols}x{rows}", "-y", str(out)],
        check=True)
    return out


def grid_sheet(video: pathlib.Path, out: pathlib.Path, start: float, duration: float, fps: float,
               cols: int, rows: int, scale: int, grid: int) -> pathlib.Path:
    """Same tiles as :func:`sheet`, but each one carries a labelled pixel grid.

    Angles in a single camera plane come out of pixel coordinates, so no scale or calibration is
    needed -- only a way to read a point off the image to a stated precision. ``grid`` is that
    precision: coordinates are labelled every ``grid`` pixels, and a marked point is read to about
    half of one cell. The frame's timestamp is printed on the tile so a sheet is self-describing.
    """
    from PIL import Image, ImageDraw, ImageFont

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clip_frames_") as tmp:
        subprocess.run(
            [_exe("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(duration),
             "-i", str(video), "-vf", f"fps={fps},scale={scale}:-2", "-y", str(pathlib.Path(tmp) / "f_%03d.png")],
            check=True)
        frames = sorted(pathlib.Path(tmp).glob("f_*.png"))[: cols * rows]
        if not frames:
            raise SystemExit(f"no frames in [{start}, {start + duration}) -- check --fps/--duration")
        opened = [Image.open(frame).convert("RGB") for frame in frames]
        tw, th = opened[0].size
        font = ImageFont.load_default(size=max(14, tw // 28))
        sheet_image = Image.new("RGB", (cols * tw, rows * th), (16, 16, 16))
        for index, frame in enumerate(opened):
            tile = frame.copy()
            overlay = Image.new("RGBA", tile.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for x in range(grid, tw, grid):
                draw.line([(x, 0), (x, th)], fill=(255, 0, 0, 90), width=1)
                if x % (grid * 2) == 0:
                    draw.text((x + 2, 2), str(x), font=font, fill=(255, 80, 80, 255))
            for y in range(grid, th, grid):
                draw.line([(0, y), (tw, y)], fill=(255, 0, 0, 90), width=1)
                if y % (grid * 2) == 0:
                    draw.text((2, y + 2), str(y), font=font, fill=(255, 80, 80, 255))
            tile = Image.alpha_composite(tile.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(tile)
            stamp = f"#{index} t={start + index / fps:.2f}s"
            draw.rectangle([0, th - 26, 12 + 10 * len(stamp), th], fill=(0, 0, 0))
            draw.text((4, th - 22), stamp, font=font, fill=(0, 255, 0))
            sheet_image.paste(tile, ((index % cols) * tw, (index // cols) * th))
        sheet_image.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Clip -> tiled frame sheet (see module docstring).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=pathlib.Path, help="local clip")
    source.add_argument("--yt-id", help="YouTube id; downloaded once into --work")
    parser.add_argument("--work", type=pathlib.Path, default=_DEFAULT_WORK)
    parser.add_argument("--height", type=int, default=1080, help="download cap, pixels")
    parser.add_argument("--start", type=float, default=0.0, help="window start, seconds")
    parser.add_argument("--duration", type=float, default=4.0, help="window length, seconds")
    parser.add_argument("--fps", type=float, default=3.0, help="samples per second in the sheet")
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--scale", type=int, default=260, help="per-tile width, pixels")
    parser.add_argument("--grid", type=int, default=0,
                        help="draw a labelled pixel grid every N px, so a point can be read off a "
                             "tile to ~half a cell (needs Pillow; angles need no other calibration)")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    video = args.video or fetch(args.yt_id, args.work, args.height)
    out = args.out or pathlib.Path(video).with_name(f"{pathlib.Path(video).stem}_s{args.start:g}_d{args.duration:g}.png")
    writer = grid_sheet if args.grid else sheet
    extra = (args.grid,) if args.grid else ()
    print(writer(video, out, args.start, args.duration, args.fps, args.cols, args.rows, args.scale, *extra))
    print(f"rows: {args.rows}, cols: {args.cols}, tile {args.scale}px, fps {args.fps} -- read row-major")


if __name__ == "__main__":
    main()
