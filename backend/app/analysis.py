import math
from typing import List, Optional, Sequence

from . import ffmpeg_tools as ff

STEP_MS = 10.0


def _moving_average(values: Sequence[float], window: int) -> List[float]:
    if window < 2:
        return list(values)
    out = []
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1] + v)
    half = window // 2
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append((prefix[hi] - prefix[lo]) / (hi - lo))
    return out


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return -90.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((len(sorted_vals) - 1) * p))))
    return sorted_vals[idx]


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _map_score(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 50.0
    return _clamp((value - lo) / (hi - lo) * 100.0)


def _nearest_silence_boundary(t: float, silences: List[tuple[float, Optional[float]]], reach: float) -> Optional[float]:
    best: Optional[float] = None
    best_dist = reach
    for s, e in silences:
        for bound in (s, e):
            if bound is None:
                continue
            d = abs(bound - t)
            if d <= best_dist and (best is None or d < best_dist):
                best = bound
                best_dist = d
    return best


def speech_regions(energy: List[dict], floor_db: float, median_db: Optional[float] = None) -> List[tuple[float, float]]:
    if median_db is None:
        median_db = sorted(e["db"] for e in energy)[len(energy) // 2] if energy else floor_db
    thresh = max(-42.0, min(-22.0, (floor_db + median_db) / 2.0 - 2.0))
    regions: List[tuple[float, float]] = []
    start: Optional[float] = None
    step = STEP_MS / 1000.0
    for e in energy:
        speaking = e["db"] > thresh
        if speaking and start is None:
            start = e["t"]
        elif not speaking and start is not None:
            regions.append((start, e["t"]))
            start = None
    if start is not None:
        regions.append((start, energy[-1]["t"] + step))
    merged: List[tuple[float, float]] = []
    for s, e in regions:
        if merged and s - merged[-1][1] < 0.4:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def classify_moment(hook: float, emotion: float, info: float, visual: float, duration: float) -> str:
    if hook >= 65 and duration <= 45:
        return "Strong hook"
    if emotion >= 65 and duration <= 45:
        return "Emotional peak"
    if info >= 70 and duration >= 45:
        return "Educational explanation"
    if visual >= 65:
        return "Visually engaging moment"
    if info >= 55 and emotion >= 45:
        return "Storytelling"
    if info >= 55:
        return "Focused take"
    return "Conversational moment"


def analyze_video(
    video_path,
    duration: float,
    target_count: int,
    target_duration: Optional[float],
    on_progress=None,
) -> dict:
    report: dict = {
        "engine": "cleapyfly-local-heuristic-v1",
        "speech_regions": [],
        "scene_change_count": 0,
        "clips": [],
    }
    if on_progress:
        on_progress(0.05, "Extracting audio track")
    wav = video_path.parent / "audio16k.wav"
    ff.extract_audio(video_path, wav)

    if on_progress:
        on_progress(0.2, "Measuring speech energy")
    energy = ff.energy_timeline(wav)
    if not energy:
        raise ff.FFmpegError("Could not read audio energy from this video (silent or corrupt audio track).")

    dbs = sorted(e["db"] for e in energy)
    noise_floor = _percentile(dbs, 0.10)
    peak_db = _percentile(dbs, 0.98)
    snr = peak_db - noise_floor

    if on_progress:
        on_progress(0.4, "Detecting sentence silences")
    silences = ff.silence_boundaries(wav)
    median_db_overall = _percentile(dbs, 0.55)
    regions = speech_regions(energy, noise_floor, median_db_overall)
    report["speech_regions"] = [
        {"start": round(s, 2), "end": round(e, 2)} for s, e in regions[:400]
    ]
    report["speech_density"] = round(
        sum(e - s for s, e in regions) / duration, 3
    ) if duration else 0.0
    report["noise_floor_db"] = round(noise_floor, 1)
    report["loudness_range_db"] = round(peak_db - noise_floor, 1)

    if on_progress:
        on_progress(0.55, "Scanning scene changes")
    scenes = ff.scene_times(video_path) if duration else []
    report["scene_change_count"] = len(scenes)

    if not regions:
        raise ff.FFmpegError("No speech detected in this video, so no clips could be proposed.")

    step = STEP_MS / 1000.0
    k = max(1, int(1.0 / step))
    smoothed = _moving_average([e["db"] for e in energy], k)
    median_db = _percentile(sorted(smoothed), 0.55)

    voices = [r for r in regions if r[1] - r[0] >= 1.2]
    if not voices:
        voices = regions

    takes: List[tuple[float, float]] = []
    gap_merge = 0.9
    for s, e in voices:
        if takes and s - takes[-1][1] <= gap_merge:
            takes[-1] = (takes[-1][0], e)
        else:
            takes.append((s, e))

    if target_duration is None:
        avg_take = sum(e - s for s, e in takes) / max(1, len(takes)) if takes else 30.0
        target_duration = float(min(90, max(30, math.floor(avg_take / 5.0) * 5)))

    scene_per_sec = len(scenes) / duration if duration > 0 else 0.0

    candidates: List[dict] = []
    for s, e in takes:
        take_len = e - s
        if take_len < max(8.0, target_duration * 0.45):
            continue
        cursor = s
        guard = 0
        while cursor < e - 4.0 and guard < 60:
            guard += 1
            raw_end = min(e, cursor + target_duration)
            if raw_end - cursor < max(10.0, target_duration * 0.55):
                break
            boundary = _nearest_silence_boundary(raw_end, silences, reach=1.2)
            end = min(boundary, e) if boundary else raw_end
            if end - cursor < max(10.0, target_duration * 0.55):
                cursor = raw_end + 0.2
                continue
            candidates.append({"start": cursor, "end": end})
            cursor = end + 0.25
    if not candidates:
        raise ff.FFmpegError(
            "The AI engine could not find any long-enough speech moments in this video. "
            "Try a custom clip duration or a longer source."
        )

    clips: List[dict] = []
    for c in candidates:
        a, b = c["start"], c["end"]
        i0 = int(a / step)
        i1 = min(len(energy) - 1, int(b / step))
        if i1 <= i0:
            continue
        seg = energy[i0:i1]
        seg_smooth = smoothed[i0:i1]
        dur = b - a

        onset = _percentile(sorted(seg_smooth[: max(1, int(1.5 / step))]), 0.8)
        body = _percentile(sorted(seg_smooth), 0.6)
        seg_sorted = sorted(e["db"] for e in seg)
        p95 = _percentile(seg_sorted, 0.95)
        p20 = _percentile(seg_sorted, 0.20)
        dynamics = p95 - p20

        speech_frames = sum(1 for e in seg if e["db"] > max(-42.0, min(-22.0, (noise_floor + median_db_overall) / 2.0 - 2.0)))
        density = speech_frames / max(1, len(seg))

        scenes_in = sum(1 for t in scenes if a <= t < b)
        scene_rate = scenes_in / dur

        start_clean = _started_clean(a, silences) >= 0.9
        end_clean = _ended_clean(b, silences, duration)

        hook = _map_score((onset - median_db) / 6.0 + 0.35, -0.4, 1.2)
        emotion = _map_score(dynamics, 6.0, 22.0)
        info = _clamp(_map_score(density, 0.45, 0.92) * 0.85 + _map_score(dur, 20, 70) * 0.15)
        context = _map_score(1.0 if start_clean else 0.35, 0.0, 1.0) * 0.5 + _map_score(
            1.0 if end_clean else 0.3, 0.0, 1.0
        ) * 0.5
        standalone = _clamp(
            _started_clean(a, silences) * 55 + end_clean * 30 + min(1.0, dur / 25.0) * 15
        )
        visual = _map_score(scene_rate, 0.005, 0.12 if scene_per_sec > 0.02 else 0.05)
        audio = _map_score(p95 - noise_floor, 15.0, 45.0)

        viral = (
            hook * 0.22
            + emotion * 0.16
            + info * 0.20
            + standalone * 0.12
            + context * 0.10
            + visual * 0.08
            + audio * 0.12
        )
        if 25 <= dur <= 65:
            viral += 3.0
        viral = _clamp(viral)

        highlights = []
        if hook >= 70:
            highlights.append("Strong opening energy")
        if emotion >= 70:
            highlights.append("High emotional dynamics")
        if info >= 70:
            highlights.append("High information value")
        if end_clean:
            highlights.append("Clean sentence ending")
        if scene_rate > 0.08:
            highlights.append("Frequent scene changes")

        clips.append(
            {
                "start": round(a, 2),
                "end": round(b, 2),
                "duration": round(dur, 2),
                "scores": {
                    "hook": round(hook, 1),
                    "emotion": round(emotion, 1),
                    "information": round(info, 1),
                    "context_completeness": round(context, 1),
                    "standalone": round(standalone, 1),
                    "visual": round(visual, 1),
                    "audio": round(audio, 1),
                    "viral_potential": round(viral, 1),
                },
                "highlights": highlights,
                "moment_type": classify_moment(hook, emotion, info, visual, dur),
            }
        )

    clips.sort(key=lambda c: c["scores"]["viral_potential"], reverse=True)
    picked: List[dict] = []
    for c in clips:
        ok = True
        for p in picked:
            overlap = max(0.0, min(c["end"], p["end"]) - max(c["start"], p["start"]))
            shortest = min(c["duration"], p["duration"])
            if shortest > 0 and overlap / shortest > 0.30:
                ok = False
                break
        if ok:
            picked.append(c)
        if len(picked) >= target_count * 3:
            break

    picked = picked[: max(1, target_count)]
    picked.sort(key=lambda c: c["start"])

    report["clips"] = picked
    report["snr_db"] = round(snr, 1)
    return report


def _started_clean(a: float, silences: List[tuple[float, Optional[float]]]) -> float:
    for s, e in silences:
        if e is not None and e <= a + 0.15 and a - e <= 1.2:
            return 1.0
    return 0.35


def _ended_clean(b: float, silences: List[tuple[float, Optional[float]]], duration: float) -> float:
    if duration and b >= duration - 0.3:
        return 1.0
    for s, _ in silences:
        if 0.1 <= b - s <= 0.9:
            return 1.0
    return 0.3
