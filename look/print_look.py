#!/usr/bin/env python3
"""print_look.py: print any clip the way "Rethink work" is printed.

The film's footage is a 2 colour risograph print on near-black paper: hot pink carries the mid-tones, cream carries
the lights, each as a screen of small dots, with a little grain. This script does that to a clip. It is a plain
version of what we used; change the numbers and make it yours.

    python3 print_look.py IN.mp4 OUT.mp4 [--size 1080] [--fps 30] [--gamma 0.85]

Needs python3 with numpy, and ffmpeg on the path. The picture is cropped to a centred square. The sound, if any, is
dropped."""
import argparse
import math
import subprocess

import numpy as np

PINK, CREAM, NIGHT = (0xE7, 0x40, 0x79), (0xFF, 0xF6, 0xE8), (0x10, 0x0D, 0x0C)


def screen(S, cell, angle):
    """The dot lattice of 1 ink: for each pixel, its distance from the middle of its dot, in cells."""
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) - S / 2
    a = math.radians(angle)
    u = (x * math.cos(a) + y * math.sin(a)) / cell
    v = (-x * math.sin(a) + y * math.cos(a)) / cell
    return np.sqrt((u - np.round(u)) ** 2 + (v - np.round(v)) ** 2)


def dots(cov, dist, cell):
    """Dots whose area is the coverage (0 to 1), with a soft edge."""
    return np.clip((np.sqrt(np.clip(cov, 0, 1) / math.pi) * 1.02 - dist) * cell * 0.9 + 0.5, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--size', type=int, default=1080)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--gamma', type=float, default=0.85, help='under 1 lifts the picture, over 1 darkens it')
    a = ap.parse_args()
    S = a.size
    cell = 4.8 * S / 1080      # the dot pitch: 4.8 px at 1080
    d_pink, d_cream = screen(S, cell, 45), screen(S, cell, 15)
    rng = np.random.default_rng(7)
    paper_grain = rng.normal(0, 0.016, (S, S)).astype(np.float32)
    read = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', a.src, '-vf', f'fps={a.fps},crop=min(iw\\,ih):min(iw\\,ih),scale={S}:{S},format=gray',
                             '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    write = subprocess.Popen(['ffmpeg', '-v', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{S}x{S}', '-r', str(a.fps), '-i', '-',
                              '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', a.out], stdin=subprocess.PIPE)
    pink, cream, night = (np.array(c, np.float32) / 255 for c in (PINK, CREAM, NIGHT))
    n = 0
    while True:
        raw = read.stdout.read(S * S)
        if len(raw) < S * S:
            break
        lum = (np.frombuffer(raw, np.uint8).reshape(S, S).astype(np.float32) / 255) ** a.gamma
        cream_cov = np.clip((lum - 0.58) / 0.36, 0, 1) ** 1.25            # the lights
        pink_cov = np.clip((lum - 0.16) / 0.46, 0, 1) ** 1.15 * (1 - 0.6 * cream_cov)      # the mid-tones
        out = np.empty((S, S, 3), np.float32)
        out[:] = night
        p = dots(pink_cov, d_pink, cell)[..., None] * 0.95
        out = out * (1 - p) + pink * p
        c = dots(cream_cov, d_cream, cell)[..., None] * 0.97
        out = out * (1 - c) + cream * c
        grain = paper_grain * 0.6 + np.random.default_rng(1000 + n).normal(0, 0.005, (S, S)).astype(np.float32)
        write.stdin.write((np.clip(out + grain[..., None], 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        n += 1
    write.stdin.close()
    write.wait()
    print(a.out, n, 'frames')


if __name__ == '__main__':
    main()
