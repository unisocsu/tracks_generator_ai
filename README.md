# Tracks Generator AI

Generate short, synchronized accompaniment tracks for arranger-keyboard experiments. GitHub Actions builds a downloadable ZIP containing WAV stems, MIDI files, a preview mix, and a JSON arrangement manifest.

## Current MVP

- **Local language model planner:** Qwen2.5-1.5B-Instruct in GGUF format, run on CPU with llama-cpp-python; no Gemini API needed to plan chords and grooves.
- **Cached model download:** the approximately 1.12 GB model is downloaded on the first GitHub Actions run and cached by Actions rather than committed to this repository.
- Deterministic synthesis creates synchronized, exact-length WAV stems: drums, bass, chords, melody, and pad.
- A MIDI file per track, arrangement.json, manifest.json, preview.wav, and a ZIP package in the internal ARRSTYLE format.
- Optional Lyria music preview remains a separate feature and still requires GEMINI_API_KEY; it is not needed for local language-model planning.

The language model creates the arrangement plan (including the chord progression and groove). The current synthesizer renders the audio with simple synthesized sounds; this does not yet produce studio-quality instrument samples or isolated audio directly from the model.

## Run it with GitHub Actions

1. Open **Actions → Generate Tracks Pack → Run workflow**.
2. Enter the accompaniment prompt, BPM, bar count, and seed.
3. Choose **local_model** for the local Qwen language model, or **built_in** for the no-model deterministic planner.
4. Leave Lyria preview off unless you specifically want the additional API-based preview.
5. Download the tracks-generator artifact from the completed run.

The first local-model run downloads about 1.12 GB. Subsequent runs can reuse the Actions cache, although GitHub may evict cached files. The model runs on the hosted CPU runner; generation time depends on model loading and prompt complexity.

## Output layout

~~~
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
│   └── ai_preview.mp3      # only when optional Lyria succeeds
└── midi/
    ├── drums.mid
    ├── bass.mid
    ├── chords.mid
    ├── melody.mid
    └── pad.mid
~~~

All locally synthesized stems share a duration and start at sample zero so they can be imported and mixed together. ARRSTYLE is this project's internal format, not a Yamaha/Korg .sty file; export to a specific arranger format remains a future stage and depends on the target keyboard model.

## Local development

Python 3.11+ is recommended.

~~~
python -m pip install -r requirements.txt
python scripts/generate_tracks.py --prompt "Upbeat pop accompaniment" --bpm 110 --bars 4 --seed 42 --output output
~~~

To use a local GGUF model, install the optional CPU runtime and set the model path:

~~~
python -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
python scripts/generate_tracks.py --planner local_model --model-path ./qwen2.5-1.5b-instruct-q4_k_m.gguf --prompt "Funky keyboard accompaniment"
~~~

Use --planner built_in to force the deterministic fallback. For API-based Lyria preview only, set GEMINI_API_KEY and pass --lyria.

## Model and security

The default language model is Qwen/Qwen2.5-1.5B-Instruct-GGUF (Q4_K_M). Read the model repository's license and usage terms before redistributing model weights. Never commit API keys; use GitHub Actions Secrets or environment variables.
