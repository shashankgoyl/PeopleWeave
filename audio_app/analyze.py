"""
Task 3 - audio property extraction.

Uses pydub (which shells out to ffmpeg) so it works regardless of what format
the browser recorded in (webm/ogg from MediaRecorder) or what a worker
uploads (mp3/wav/m4a/...).

Extracted per the spec:
  - duration_seconds
  - sample_rate_hz
  - bitrate_kbps        (derived from actual file size / duration - meaningful
                          for compressed formats, not just the container header)
  - loudness_db         (RMS-based dBFS - "how loud is this clip", pydub's dBFS)
  - noise_estimate       (bonus, rough heuristic - see note below)

Noise/quality heuristic (bonus): we slice the clip into 50ms windows, take the
dBFS of each window, and compare the loud windows (90th percentile - "signal")
to the quiet windows (10th percentile - "noise floor"). That gap is a crude
proxy for SNR. It is NOT a real noise-suppression or ASR-quality metric - a
proper version would use something like WADA-SNR or a trained model - but for
a submission-triage flag ("does this recording need a human to re-listen
before we pay for it") it's a reasonable few-lines-of-code approximation.
"""
import os
from pydub import AudioSegment


def _snr_estimate_db(seg: AudioSegment) -> float:
    window_ms = 50
    levels = []
    for start in range(0, len(seg), window_ms):
        chunk = seg[start:start + window_ms]
        if len(chunk) == 0:
            continue
        db = chunk.dBFS
        if db == float("-inf"):
            continue
        levels.append(db)
    if len(levels) < 4:
        return 40.0  # too short to judge, assume clean
    levels.sort()
    n = len(levels)
    noise_floor = levels[max(0, int(n * 0.10) - 1)]
    signal_level = levels[min(n - 1, int(n * 0.90))]
    return signal_level - noise_floor


def classify_noise(snr_db: float) -> str:
    if snr_db >= 30:
        return "clean"
    if snr_db >= 15:
        return "moderate_noise"
    return "noisy"


def analyze_audio(file_path: str) -> dict:
    file_size_bytes = os.path.getsize(file_path)
    seg = AudioSegment.from_file(file_path)

    duration_seconds = round(len(seg) / 1000.0, 3)
    sample_rate_hz = seg.frame_rate

    bitrate_kbps = None
    if duration_seconds > 0:
        bitrate_kbps = round((file_size_bytes * 8) / duration_seconds / 1000, 1)

    loudness_db = None
    if seg.dBFS != float("-inf"):
        loudness_db = round(seg.dBFS, 1)

    snr = _snr_estimate_db(seg)
    noise_estimate = classify_noise(snr)

    return {
        "duration_seconds": duration_seconds,
        "sample_rate_hz": sample_rate_hz,
        "bitrate_kbps": bitrate_kbps,
        "loudness_db": loudness_db,
        "noise_estimate": noise_estimate,
        "channels": seg.channels,
        "file_size_bytes": file_size_bytes,
    }


if __name__ == "__main__":
    import sys
    import json
    print(json.dumps(analyze_audio(sys.argv[1]), indent=2))
