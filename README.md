# Tracks Generator AI

Generate short, synchronized accompaniment tracks for arranger-keyboard style experiments. GitHub Actions builds a downloadable ZIP containing WAV stems, MIDI files, a preview mix, and a JSON manifest.

## Current MVP

- Optional Gemini planning using `GEMINI_API_KEY` (model: `gemini-3.8-flash`).
- Optional Lyria 3 Clip generation for an additional 30-second AI music preview.
- Deterministic, local synthesis for synchronized, exact-length WAV stems: drums, bass, chords, melody, and pad.
- MIDI file per track, `arrangement.json`, `manifest.json`, and `preview.wav`.
- ZIP artifact downloadable from the GitHub Actions run.

The local synthesizer is intentionally the reliable stem generator in this first version. Lyria generates a separate musical preview; it does not yet provide isolated stems or exact arranger-style sections.

## Run it

1. Open **Settings → Secrets and variables → Actions** in this repository.
2. Add a repository secret named `GEMINI_API_KEY` with your Gemini API key. The workflow still runs without it and uses a deterministic fallback arrangement.
3. Open **Actions → Generate Tracks Pack → Run workflow**.
4. Enter a prompt, BPM, bar count, and seed. Enable **Generate Lyria AI preview** to request an extra AI-generated music clip.
5. Download the `tracks-generator-…` artifact from the completed run.

The workflow does not print the API key. Gemini API usage and any Lyria generation may be subject to Google's account limits, pricing, and model availability.

## Output layout

```
tracks-generator.zip
├── manifest.json
├── arrangement.json
├── preview.wav
├── audio/
│   ├── drums.wav
│   ├── bass.wav
│   ├── chords.wav
│   ├── melody.wav
│   ├── pad.wav
│   └── ai_preview.mp3      # only when Lyria succeeds
└── midi/
    ├── drums.mid
    ├── bass.mid
    ├── chords.mid
    ├── melody.mid
    └── pad.mid
```

All locally synthesized stems have the same duration and begin at time zero so they can be imported and mixed together. The first release uses the project's own JSON arrangement format; export to a specific Yamaha/Korg STY format is a separate future stage and depends on the target keyboard model.

## Local development

Python 3.11+ is recommended.

```bash
python -m pip install -r requirements.txt
python scripts/generate_tracks.py --prompt "Upbeat pop accompaniment" --bpm 110 --bars 4 --seed 42 --output output
```

To request Gemini planning locally, set `GEMINI_API_KEY` in your environment. To request Lyria as well, add `--lyria`.

## Security

Never commit API keys. Use GitHub Actions Secrets or environment variables. Generated audio and the manifest are outputs, not executable code.
