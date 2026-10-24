"""Extract the head-related impulse responses the audio engine uses from a SOFA file.

    pip install h5py numpy
    curl -LO https://sofacoustics.org/data/database/mit/mit_kemar_normal_pinna.sofa
    python3 -m tools.hrir_extract mit_kemar_normal_pinna.sofa hyperx_linux/data/hrtf-mit-kemar

Writes one 24-bit stereo WAV per direction, e<elevation>_a<azimuth>.wav (azimuth 0 = front, 90 = left,
as PipeWire counts): every 5° on the horizontal plane, one below the front for the LFE, and every 30°
at +40°. All files share one gain, so the level differences between directions are kept.
"""
import os
import sys
import wave

import h5py
import numpy as np


def main(src: str, out: str) -> None:
    f = h5py.File(src, "r")
    ir, pos, fs = f["Data.IR"][()], f["SourcePosition"][()], int(f["Data.SamplingRate"][()][0])
    want = [(0, a) for a in range(0, 360, 5)] + [(-40, 0)] + [(40, a) for a in range(0, 360, 30)]
    picked = {}
    for el, az in want:
        distance = np.hypot(((pos[:, 0] - az + 180) % 360) - 180, pos[:, 1] - el)
        i = int(np.argmin(distance))
        if distance[i] > 3:
            raise SystemExit(f"no measurement near elevation {el}, azimuth {az}")
        picked[(el, az)] = ir[i]
    peak = max(np.abs(x).max() for x in picked.values())
    os.makedirs(out, exist_ok=True)
    for (el, az), x in picked.items():
        pcm = np.round(np.clip(x.T / peak * 0.999, -1, 1) * (2 ** 23 - 1)).astype("<i4")  # frames x 2
        data = b"".join(int(v).to_bytes(4, "little", signed=True)[:3] for v in pcm.reshape(-1))
        with wave.open(f"{out}/e{el:+03d}_a{az:03d}.wav", "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(3)
            w.setframerate(fs)
            w.writeframes(data)
    print(f"{len(picked)} impulse responses, {fs} Hz")


if __name__ == "__main__":
    main(*sys.argv[1:3])
