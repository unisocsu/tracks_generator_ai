#!/usr/bin/env python3
"""Generate synchronized keyboard-accompaniment WAV stems, MIDI and an ARRSTYLE ZIP."""

import argparse, base64, hashlib, json, os, sys, urllib.request, wave, zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import mido

SR = 22050
NAMES = ("drums", "bass", "chords", "melody", "pad")
ROOTS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
GROOVES = ("pop_rock", "four_on_floor", "funk", "reggae", "half_time", "latin", "swing", "electronic")


def groove_for(prompt):
    p = prompt.lower()
    for words, name in [(("reggae", "רגאיי"), "reggae"), (("funk", "פאנק"), "funk"),
                        (("latin", "salsa", "cumbia"), "latin"), (("house", "dance", "דאנס"), "four_on_floor"),
                        (("swing", "shuffle"), "swing"), (("electronic", "edm", "techno"), "electronic")]:
        if any(w in p for w in words):
            return name
    return "pop_rock"


def parse_chord(symbol):
    s = str(symbol or "Am").strip()
    if not s or s[0].upper() not in ROOTS:
        return 9, [0, 3, 7]
    root, rest = ROOTS[s[0].upper()], s[1:]
    if rest.startswith("#"):
        root += 1
        rest = rest[1:]
    elif rest.startswith("b"):
        root -= 1
        rest = rest[1:]
    q = rest.lower()
    if q.startswith("maj7"): ints = [0, 4, 7, 11]
    elif q.startswith("m7") or q.startswith("min7"): ints = [0, 3, 7, 10]
    elif q.startswith("7"): ints = [0, 4, 7, 10]
    elif q.startswith("dim"): ints = [0, 3, 6]
    elif q.startswith("sus2"): ints = [0, 2, 7]
    elif q.startswith("sus4"): ints = [0, 5, 7]
    elif q.startswith("m"): ints = [0, 3, 7]
    else: ints = [0, 4, 7]
    return root % 12, ints


def get_plan(prompt, bpm, bars, seed):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    raw = None
    if key:
        task = (
            "Return JSON only for a short keyboard accompaniment loop. Keep it instrumental. "
            "Return keys title, genre, mood, key, chord_progression, groove, melody_density, notes. "
            "Use one chord per bar and these grooves: " + ", ".join(GROOVES) + ". "
            "Chord examples: Am, F, C, G, Dm, E7, Bb, Gmaj7."
            + chr(10) + "Prompt: " + prompt + chr(10)
            + "Tempo: " + str(bpm) + " BPM, meter 4/4, exactly " + str(bars) + " bars, seed " + str(seed) + "."
            + chr(10) + 'Example JSON: {"title":"Keyboard Groove","genre":"pop","mood":"upbeat","key":"Am",'
            + '"chord_progression":["Am","F","C","G"],"groove":"pop_rock","melody_density":2,"notes":"brief note"}'
        )
        body = {"contents": [{"role": "user", "parts": [{"text": task}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7, "maxOutputTokens": 1000}}
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
            text = "".join(p.get("text", "") for p in result["candidates"][0]["content"]["parts"] if p.get("text")).strip()
            raw = json.loads(text)
            if not isinstance(raw, dict):
                raw = None
            else:
                print("Gemini arrangement plan received.")
        except Exception as exc:
            print("Gemini planner unavailable (" + type(exc).__name__ + "); using built-in arrangement.")
    else:
        print("GEMINI_API_KEY missing; using built-in arrangement.")
    fallback = ["Am", "F", "C", "G"] if "minor" not in prompt.lower() else ["Am", "F", "Dm", "E7"]
    fallback = [fallback[i % len(fallback)] for i in range(bars)]
    chords = raw.get("chord_progression") if raw and isinstance(raw.get("chord_progression"), list) else fallback
    chords = (chords + fallback * (bars + 1))[:bars]
    chords = [str(ch) if isinstance(ch, str) and ch else "Am" for ch in chords]
    groove = str(raw.get("groove") if raw else groove_for(prompt)).lower().replace("-", "_").replace(" ", "_")
    groove = {"pop": "pop_rock", "rock": "pop_rock", "house": "four_on_floor", "edm": "electronic"}.get(groove, groove)
    if groove not in GROOVES:
        groove = groove_for(prompt)
    try:
        density = max(1, min(4, int(raw.get("melody_density", 2) if raw else 2)))
    except Exception:
        density = 2
    return {
        "format": "ARRSTYLE", "format_version": "0.1.0",
        "title": str(raw.get("title", "Generated Keyboard Groove") if raw else "Generated Keyboard Groove")[:90],
        "genre": str(raw.get("genre", groove) if raw else groove)[:80],
        "mood": str(raw.get("mood", "upbeat") if raw else "upbeat")[:80],
        "key": str(raw.get("key", chords[0]) if raw else chords[0])[:20],
        "prompt": prompt, "bpm": bpm, "meter": "4/4", "bars": bars, "seed": seed,
        "groove": groove, "chord_progression": chords, "melody_density": density,
        "planner": "gemini-3.8-flash" if raw else "built-in-fallback",
        "sections": [{"name": "Main A", "start_bar": 0, "bars": bars}]
    }


def build_events(plan):
    out = {n: [] for n in NAMES}
    import random
    rng = random.Random(plan["seed"])
    for bar, chord in enumerate(plan["chord_progression"]):
        b = bar * 4.0
        root, ints = parse_chord(chord)
        bass = 36 + root
        if plan["groove"] in ("four_on_floor", "electronic"):
            kick, snare, hats, bb = [0, 1, 2, 3], [1, 3], [i * .5 for i in range(8)], [0, 1, 2, 3]
        elif plan["groove"] == "funk":
            kick, snare, hats, bb = [0, 1.5, 2.5], [1, 3], [i * .5 for i in range(8)], [0, 1, 1.5, 2, 3, 3.5]
        elif plan["groove"] == "reggae":
            kick, snare, hats, bb = [0, 2.5], [2, 3], [0, 1, 2, 3], [0, 1.5, 2.5]
        elif plan["groove"] == "half_time":
            kick, snare, hats, bb = [0, 2.5], [2], [i * .5 for i in range(8)], [0, 2]
        elif plan["groove"] == "swing":
            kick, snare, hats, bb = [0, 2], [1, 3], [0, .67, 1, 1.67, 2, 2.67, 3, 3.67], [0, 2]
        else:
            kick, snare, hats, bb = [0, 2], [1, 3], [i * .5 for i in range(8)], [0, 2]
        for t in kick: out["drums"].append((b + t, .16, 36, 110))
        for t in snare: out["drums"].append((b + t, .14, 38, 90))
        for i, t in enumerate(hats): out["drums"].append((b + t, .08, 46 if i == 7 and plan["groove"] == "funk" else 42, 62 if i % 2 else 72))
        if plan["groove"] == "latin":
            for t in (.5, 1.5, 2.5, 3.5): out["drums"].append((b + t, .09, 37, 68))
        for i, t in enumerate(bb):
            out["bass"].append((b + t, .7 if len(bb) <= 3 else .38, bass if i % 2 == 0 else bass + 7, 95))
        stabs = [0, 2] if plan["groove"] in ("funk", "latin") else [0]
        for t in stabs:
            for n in ints: out["chords"].append((b + t, .65 if len(stabs) > 1 else 3.7, 48 + root + n, 72))
        for n in ints: out["pad"].append((b, 3.85, 60 + root + n, 44))
        density = plan["melody_density"]
        mt = [0, 2] if density == 1 else [0, 1, 2, 3] if density == 2 else [0, .5, 1.5, 2, 3, 3.5] if density == 3 else [i * .5 for i in range(8)]
        pool = [72 + root + n for n in ints]
        if len(pool) < 3: pool.append(72 + root + 12)
        for i, t in enumerate(mt): out["melody"].append((b + t, .35, pool[(i + rng.randrange(len(pool))) % len(pool)], 74))
    return out


def synth(name, pitch, velocity, duration, rng):
    count = max(1, int(duration * SR))
    t = np.arange(count, dtype=np.float32) / SR
    amp = velocity / 127.0
    if name == "drums":
        if pitch == 36:
            phase = 2 * np.pi * (45 * t + 3.5 * (1 - np.exp(-t * 22)))
            signal = np.sin(phase) * np.exp(-t * 17)
        elif pitch in (37, 38):
            noise = rng.normal(0, 1, count).astype(np.float32)
            signal = noise * np.exp(-t * 25) + .2 * np.sin(2 * np.pi * 180 * t) * np.exp(-t * 24)
        else:
            noise = rng.normal(0, 1, count).astype(np.float32)
            prior = np.concatenate((np.zeros(1, dtype=np.float32), noise[:-1]))
            signal = (noise - .8 * prior) * np.exp(-t * (42 if pitch == 42 else 18))
        return (signal * amp * .35).astype(np.float32)
    hz = 440 * (2 ** ((pitch - 69) / 12))
    attack = .12 if name == "pad" else .008
    release = min(.12 if name == "pad" else .05, max(.01, duration * .4))
    env = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, duration - t) / release)
    signal = np.sin(2 * np.pi * hz * t) + .17 * np.sin(2 * np.pi * hz * 2 * t)
    gain = {"bass": .42, "chords": .25, "melody": .25, "pad": .18}[name]
    return (signal * env * amp * gain).astype(np.float32)


def render(name, events, total, bpm, seed):
    audio = np.zeros(total, dtype=np.float32)
    beat_sec = 60 / bpm
    rng = np.random.default_rng(seed + NAMES.index(name) * 1009)
    for beat, duration, pitch, velocity in events:
        start = max(0, int(beat * beat_sec * SR))
        voice = synth(name, pitch, velocity, max(.02, duration * beat_sec), rng)
        end = min(total, start + len(voice))
        if start < total: audio[start:end] += voice[:end - start]
    peak = float(np.max(np.abs(audio))) if audio.size else 0
    if peak: audio *= min(1, .92 / peak)
    return audio


def write_wav(path, audio):
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(SR); wav.writeframes(pcm.tobytes())


def write_midi(path, name, events, bpm):
    mid = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack(); mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    channel = 9 if name == "drums" else 0
    timed = []
    for beat, dur, pitch, vel in events:
        start, end = max(0, round(beat * 480)), max(round(beat * 480) + 1, round((beat + dur) * 480))
        pitch, vel = int(max(0, min(127, pitch))), int(max(1, min(127, vel)))
        timed.append((start, 1, mido.Message("note_on", channel=channel, note=pitch, velocity=vel)))
        timed.append((end, 0, mido.Message("note_off", channel=channel, note=pitch, velocity=0)))
    timed.sort(key=lambda x: (x[0], x[1]))
    prev = 0
    for tick, _, msg in timed:
        msg.time = max(0, tick - prev); track.append(msg); prev = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    path.parent.mkdir(parents=True, exist_ok=True); mid.save(str(path))


def request_lyria(prompt, bpm, path):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Lyria requested but GEMINI_API_KEY is missing; skipping AI preview.")
        return
    prompt_text = "Instrumental only, no vocals. Short, loop-friendly keyboard accompaniment at " + str(bpm) + " BPM, 4/4. " + prompt + ". Tight drums, bass and chords."
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps({"model": "lyria-3-clip-preview", "input": prompt_text}).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as response: result = json.loads(response.read().decode())
        data = None
        for step in result.get("steps", []):
            if step.get("type") == "model_output":
                for block in step.get("content", []):
                    if block.get("type") == "audio" and isinstance(block.get("data"), str): data = block["data"]
        if not data and isinstance(result.get("output_audio"), dict): data = result["output_audio"].get("data")
        if not data: raise ValueError("No audio block in response")
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(base64.b64decode(data))
        print("Lyria AI preview saved.")
    except Exception as exc:
        print("Lyria preview failed (" + type(exc).__name__ + "); continuing without it.")


def create_package(package, out, plan):
    assets = []
    for f in sorted(package.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            assets.append({"path": f.relative_to(package).as_posix(), "size_bytes": f.stat().st_size,
                           "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    manifest = {
        "format": "ARRSTYLE", "format_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "title": plan["title"], "prompt": plan["prompt"],
        "generation": {"planner": plan["planner"], "audio_engine": "tracks-generator-synth-v1",
                       "lyria_preview": (package / "audio" / "ai_preview.mp3").exists()},
        "settings": {"bpm": plan["bpm"], "meter": "4/4", "bars": plan["bars"],
                     "duration_seconds": round(plan["bars"] * 4 * 60 / plan["bpm"], 6),
                     "sample_rate_hz": SR, "channels": 1, "encoding": "PCM 16-bit",
                     "seed": plan["seed"], "groove": plan["groove"], "key": plan["key"]},
        "sections": plan["sections"],
        "tracks": [{"name": n, "wav": "audio/" + n + ".wav", "midi": "midi/" + n + ".mid"} for n in NAMES],
        "assets": assets,
        "notes": ["WAV stems share a duration and start at sample zero.",
                  "ARRSTYLE is this project's internal format, not a Yamaha/Korg STY file.",
                  "Optional Lyria audio is a separate mixed preview, not isolated stems."]
    }
    (package / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "tracks-generator.zip"
    if archive.exists(): archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(package.rglob("*")):
            if f.is_file(): zf.write(f, f.relative_to(package).as_posix())
    return archive


def generate(prompt, bpm, bars, seed, out, use_lyria):
    plan = get_plan(prompt, bpm, bars, seed)
    package = out / "package"
    if package.exists():
        import shutil
        shutil.rmtree(package)
    (package / "audio").mkdir(parents=True); (package / "midi").mkdir(parents=True)
    events = build_events(plan)
    total = round(bars * 4 * 60 / bpm * SR)
    stems = {}
    for name in NAMES:
        stems[name] = render(name, events[name], total, bpm, seed)
        write_wav(package / "audio" / (name + ".wav"), stems[name])
        write_midi(package / "midi" / (name + ".mid"), name, events[name], bpm)
    mix = np.zeros(total, dtype=np.float32)
    gains = {"drums": .9, "bass": .9, "chords": .72, "melody": .55, "pad": .45}
    for name in NAMES: mix += stems[name] * gains[name]
    peak = float(np.max(np.abs(mix))) if mix.size else 0
    if peak: mix *= min(1, .94 / peak)
    write_wav(package / "preview.wav", mix)
    structured = dict(plan)
    structured["tracks"] = {name: [{"start_beat": round(a, 4), "duration_beats": round(d, 4), "midi_note": p, "velocity": v}
                                  for a, d, p, v in events[name]] for name in NAMES}
    (package / "arrangement.json").write_text(json.dumps(structured, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    if use_lyria: request_lyria(prompt, bpm, package / "audio" / "ai_preview.mp3")
    archive = create_package(package, out, plan)
    print("Planner: " + plan["planner"] + " | " + plan["groove"] + " | " + str(bpm) + " BPM | " + str(bars) + " bars")
    print("Generated 5 WAV stems, 5 MIDI files, mix, manifest and ZIP: " + str(archive))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompt", default=os.environ.get("TRACKS_PROMPT", "Upbeat pop keyboard accompaniment"))
    p.add_argument("--bpm", type=int, default=int(os.environ.get("TRACKS_BPM", "110")))
    p.add_argument("--bars", type=int, default=int(os.environ.get("TRACKS_BARS", "4")))
    p.add_argument("--seed", type=int, default=int(os.environ.get("TRACKS_SEED", "42")))
    p.add_argument("--output", type=Path, default=Path("output"))
    p.add_argument("--lyria", action="store_true")
    a = p.parse_args()
    if not a.prompt.strip(): p.error("prompt cannot be empty")
    if not 45 <= a.bpm <= 220: p.error("BPM must be 45-220")
    if not 1 <= a.bars <= 16: p.error("bars must be 1-16")
    try: generate(a.prompt.strip(), a.bpm, a.bars, a.seed, a.output.resolve(), a.lyria)
    except Exception as exc:
        print("Generation failed: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
