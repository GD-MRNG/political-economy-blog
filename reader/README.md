# Political Economy Reader

A terminal TTS reader for the Political Economy Blog, powered by [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) — an 82M-parameter open-weight speech model that runs entirely on CPU.

---

## Quick Start

```bash
# One-time system dependencies (macOS)
brew install espeak-ng portaudio

# Run
cd reader
uv run reader.py
```

UV creates the virtual environment and installs all Python dependencies automatically on first run. Kokoro model weights and voices are downloaded from Hugging Face on first use (~300 MB, cached in `~/.cache/huggingface/` after that).

---

## Architecture

```
reader/
├── extractor.py      # Content extraction module
├── reader.py         # TTS CLI — imports extractor
├── pyproject.toml    # Python dependencies (managed by UV)
├── uv.lock           # Pinned dependency versions
└── README.md
```

### `extractor.py` — Content Module

Parses Jekyll Markdown post files and returns structured content as plain Python dicts. Has no dependency on the TTS stack, so it can be imported and used independently.

**Public API:**

```python
get_posts() -> dict[str, list[Path]]
# Returns all posts grouped by type, sorted newest-first.
# Keys: "global", "singapore", "tech"

extract(filepath) -> list[dict[str, str]]
# Parses a post file and returns a list of {"title": str, "text": str} dicts.
```

**Extraction logic by post type:**

| Type | Detection | Output |
|---|---|---|
| Global Briefing | `Global-Briefing` in filename | Up to 15 chunks: Executive Summary + one per region |
| Singapore Briefing | `Singapore-Briefing` in filename | 1 chunk: full post body |
| Technology Briefing | `Tech-Briefing` or `Technology-Briefing` in filename | 1 chunk: full post body |

For **Global Briefings**, the Executive Summary is extracted from between the `<!-- preview-start -->` marker and the first region heading. Each region's content comes from its `<details><summary>Current Assessment</summary>` block. For **Singapore and Technology Briefings**, content runs from `<!-- preview-start -->` (or the end of YAML frontmatter in older posts) to the `← Back to Home` footer link.

### `reader.py` — TTS CLI

Drives the interactive menu and handles all TTS generation and playback.

**Key globals** (edit to customise):

```python
VOICE_PRIMARY   = "af_bella"   # base voice
VOICE_SECONDARY = "am_adam"    # blend voice
VOICE_MIX       = 0.8          # 80% primary, 20% secondary
LANG_CODE       = "a"          # American English
SAMPLE_RATE     = 24_000       # Hz (fixed by Kokoro)
DEVICE          = "cpu"
```

---

## Workflow

```
uv run reader.py
       │
       ▼
  ┌─────────────────────────────────────────┐
  │  Post menu: 9 most recent briefings     │
  │  (3 per type, sorted by date) + Exit    │
  └──────────────────┬──────────────────────┘
                     │ user picks number
                     ▼
       TTS announces: "Global Briefing,
                       15 June 2026."
                     │
                     ▼
           ┌─────────────────────┐
           │ extractor.extract() │
           └──────────┬──────────┘
                      │
          ┌───────────┴───────────┐
          │ 1 chunk               │ 15 chunks
          │ (SG / Tech)           │ (Global)
          ▼                       ▼
      TTS announces          Section menu
      section title    ┌─────────────────────┐
      then reads       │ Regions + ← Back    │
      ────────────     └──────────┬──────────┘
      loops back to               │ user picks
      post menu                   ▼
                         TTS announces section
                         title then reads
                         ─────────────────
                         loops back to
                         section menu
```

Every reading begins with the **post name and date** spoken aloud (e.g. *"Global Briefing, 15 June 2026."*), followed by the **section title** (e.g. *"Global."* or *"Singapore Briefing."*), then the content. This means a listener always knows exactly where they are before the prose begins.

After finishing, the reader loops back automatically — to the section menu for Global Briefings, or to the post menu for Singapore and Technology Briefings. Press **Ctrl-C at any menu prompt** to exit.

---

## Audio Pipeline

```
KPipeline (Kokoro)          sd.OutputStream
──────────────────          ───────────────
generates segment 1  ──▶   stream.write(seg 1)  ──▶  speakers
generates segment 2  ──▶   stream.write(seg 2)
generates segment 3  ──▶   ...
        │
   Queue(maxsize=2)
   buffers ahead
```

Text is split at blank lines (`\n\n+`) rather than every newline, so headings flow into their paragraphs as one segment rather than generating a pause between each line.

A **background producer thread** generates segments and places them into a bounded queue. The **main thread** reads from the queue and writes into a single open `sd.OutputStream`. Because the stream stays open for the entire reading session, there is no device stop/start between segments — audio is continuous and gapless.

Pressing **Ctrl-C during reading** stops playback immediately and returns to the menu.

---

## Voice Blending

Kokoro voices are latent vectors stored as PyTorch tensors. Blending two voices is a weighted average of their tensors:

```python
mixed = bella * 0.8 + adam * 0.2
```

The blended tensor is computed once at startup and reused for the entire session. To change the voice, edit `VOICE_PRIMARY`, `VOICE_SECONDARY`, and `VOICE_MIX` at the top of `reader.py`. Available voices are listed at [hexgrad/Kokoro-82M/voices](https://huggingface.co/hexgrad/Kokoro-82M/tree/main/voices).

---

## Dependencies

| Package | Purpose |
|---|---|
| `kokoro>=0.9.2` | TTS model and generation pipeline |
| `torch` | Tensor operations for voice blending |
| `huggingface-hub` | Downloads model weights and voice files |
| `sounddevice` | Audio output via PortAudio |
| `numpy` | Audio array handling |
| `rich` | Coloured terminal UI |

System: `espeak-ng` (phonemisation), `portaudio` (audio I/O) — both via `brew install espeak-ng portaudio` on macOS.
