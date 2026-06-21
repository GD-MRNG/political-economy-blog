"""Political Economy Reader — terminal TTS for blog briefings.

Usage:
    cd reader
    uv run reader.py
"""

from __future__ import annotations

import queue
import re
import threading
from datetime import datetime
import torch
from pathlib import Path
from huggingface_hub import hf_hub_download
from kokoro import KPipeline
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import sounddevice as sd

import extractor

# ── Global config ─────────────────────────────────────────────────────────────

KOKORO_REPO     = "hexgrad/Kokoro-82M"
VOICE_PRIMARY   = "af_bella"       # base voice (American Female)
VOICE_SECONDARY = "am_adam"        # blend voice (American Male)
VOICE_MIX       = 0.8              # weight of primary; secondary = 1 - VOICE_MIX
LANG_CODE       = "a"              # 'a' = American English
SAMPLE_RATE     = 24_000           # Hz — fixed by Kokoro
DEVICE          = "cpu"

console = Console()

# ── TTS pipeline (lazy-initialised on first call to speak()) ──────────────────

_pipeline: KPipeline | None = None
_voice: torch.Tensor | None = None


def _init_pipeline() -> None:
    global _pipeline, _voice
    if _pipeline is not None:
        return
    with console.status("[dim]Loading Kokoro TTS pipeline…[/dim]"):
        _pipeline = KPipeline(lang_code=LANG_CODE, device=DEVICE)
        bella = torch.load(
            hf_hub_download(KOKORO_REPO, f"voices/{VOICE_PRIMARY}.pt"),
            weights_only=True,
        )
        adam = torch.load(
            hf_hub_download(KOKORO_REPO, f"voices/{VOICE_SECONDARY}.pt"),
            weights_only=True,
        )
        _voice = bella * VOICE_MIX + adam * (1.0 - VOICE_MIX)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip Markdown and HTML so Kokoro reads clean prose."""
    text = re.sub(r"<[^>]+>", " ", text)                         # HTML tags
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)      # **bold** *italic*
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)   # ## headings
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)         # [text](url)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)    # list bullets
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)    # 1. numbered lists
    text = re.sub(r"^---+$", ".", text, flags=re.MULTILINE)      # hr → brief pause
    text = re.sub(r"https?://\S+", "", text)                      # bare URLs
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Playback ──────────────────────────────────────────────────────────────────

# Split only at blank lines (paragraph breaks), not every newline.
# This keeps headings attached to their following text, eliminating the gap
# that occurs when Kokoro generates each line as a separate segment.
_SPLIT_PATTERN = r"\n\n+"


def speak(text: str, title: str = "") -> None:
    _init_pipeline()
    assert _pipeline is not None and _voice is not None

    clean = (f"{title}.\n\n" if title else "") + _clean(text)
    console.print(
        Panel("[bold green]Reading[/bold green]  ·  [dim]Ctrl-C to stop[/dim]", expand=False)
    )

    # Producer: generate audio segments in a background thread so the next
    # segment is ready before the current one finishes playing.
    audio_q: queue.Queue = queue.Queue(maxsize=2)
    stop_evt = threading.Event()

    def _generate() -> None:
        try:
            for _, _, audio in _pipeline(clean, voice=_voice, split_pattern=_SPLIT_PATTERN):
                if stop_evt.is_set():
                    break
                if hasattr(audio, "numpy"):
                    audio = audio.numpy()
                audio_q.put(audio)
        finally:
            audio_q.put(None)  # sentinel — signals end of stream

    threading.Thread(target=_generate, daemon=True).start()

    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            while True:
                audio = audio_q.get()
                if audio is None:
                    break
                stream.write(audio.astype("float32"))
    except KeyboardInterrupt:
        stop_evt.set()
        audio_q.put(None)
        console.print("\n[yellow]Stopped.[/yellow]")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _spoken_date(date_str: str) -> str:
    """'2026-06-15' → '15 June 2026'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%B')} {dt.year}"


# ── Menu helper ───────────────────────────────────────────────────────────────

def _pick(items: list[tuple[str, str]], title: str) -> int:
    """Print a numbered menu and return the chosen 0-based index."""
    console.print(f"\n[bold]{title}[/bold]\n")
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column(style="white")
    table.add_column(style="dim")
    for i, (label, meta) in enumerate(items, 1):
        table.add_row(str(i), label, meta)
    console.print(table)

    while True:
        raw = console.input("[cyan]>[/cyan] ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw) - 1
        console.print(f"  [red]Enter 1–{len(items)}[/red]")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold blue]Political Economy Reader[/bold blue]",
        subtitle="[dim]Kokoro TTS · CPU[/dim]",
    ))

    try:
        while True:
            # Post selection menu
            posts = extractor.get_posts()
            options: list[tuple[str, str, Path]] = []
            for key, (label, _) in extractor.POST_TYPES.items():
                for path in posts[key][:3]:
                    options.append((label, path.name[:10], path))
            options.sort(key=lambda x: x[1], reverse=True)
            options = options[:9]

            idx = _pick(
                [(label, date) for label, date, _ in options] + [("Exit", "")],
                "Select a briefing:",
            )
            if idx == len(options):
                break

            label, date_str, chosen_path = options[idx]
            speak(f"{label}, {_spoken_date(date_str)}.")

            chunks = extractor.extract(chosen_path)

            if len(chunks) == 1:
                speak(chunks[0]["text"], chunks[0]["title"])
            else:
                while True:
                    chunk_idx = _pick(
                        [(c["title"], "") for c in chunks] + [("← Back", "")],
                        "Select a section:",
                    )
                    if chunk_idx == len(chunks):
                        break
                    speak(chunks[chunk_idx]["text"], chunks[chunk_idx]["title"])

    except KeyboardInterrupt:
        pass

    console.print("\n[dim]Goodbye.[/dim]\n")


if __name__ == "__main__":
    main()
