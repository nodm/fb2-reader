"""CLI entry-point for fb2mp3.

Usage
-----
    fb2mp3 <input.fb2> --lang <en|uk|ru> (--speaker NAME | --voice FILE) [OPTIONS]
"""
from __future__ import annotations

import argparse
import logging
import os


def build_parser() -> argparse.ArgumentParser:
    """Return the configured argument parser."""
    parser = argparse.ArgumentParser(
        prog="fb2mp3",
        description="Convert an FB2 eBook to an MP3 audiobook using XTTS v2.",
    )
    parser.add_argument("input", help="Path to the input .fb2 file")
    parser.add_argument(
        "--lang",
        required=True,
        choices=["en", "uk", "ru"],
        help="Language code of the book",
    )
    parser.add_argument(
        "--speaker",
        default=None,
        help="Built-in XTTS v2 speaker name",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Path to reference WAV file for voice cloning",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output path. Without --split-chapters: path/filename for the single MP3 "
            "(default: <book_title>.mp3). With --split-chapters: path to the output "
            "directory where per-chapter MP3 files will be written "
            "(default: <book_title>/)."
        ),
    )
    parser.add_argument(
        "--split-chapters",
        action="store_true",
        help="Output one MP3 per chapter instead of a single file",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        choices=["cuda", "cpu"],
        help="Inference device (default: cuda)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments, validate inputs, and run the pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args(argv)

    # --- Validation ---

    # Exactly one of --speaker / --voice must be provided.
    if bool(args.speaker) == bool(args.voice):
        parser.error("Specify exactly one of --speaker or --voice")

    # --voice file must exist and be a .wav file.
    if args.voice is not None:
        if not os.path.isfile(args.voice):
            parser.error(f"Reference audio file not found: {args.voice}")
        if not args.voice.lower().endswith(".wav"):
            parser.error(f"Reference audio file must be a .wav file: {args.voice}")

    # Input file must exist and end in .fb2.
    if not os.path.isfile(args.input):
        parser.error(f"Input file not found: {args.input}")
    if not args.input.lower().endswith(".fb2"):
        parser.error(f"Input file must be an .fb2 file: {args.input}")

    # When --split-chapters is set, --output is interpreted as a directory path.
    # Warn the user if the path looks like a file (i.e. ends with .mp3).
    if args.split_chapters and args.output and args.output.lower().endswith(".mp3"):
        parser.error(
            "--output must be a directory path when --split-chapters is set, "
            f"but got a .mp3 filename: {args.output!r}"
        )

    # --- Build config and run ---
    from .pipeline import Pipeline, PipelineConfig

    config = PipelineConfig(
        input_path=args.input,
        output_path=args.output,
        lang=args.lang,
        speaker=args.speaker,
        voice=args.voice,
        split_chapters=args.split_chapters,
        device=args.device,
    )

    Pipeline(config).run()


if __name__ == "__main__":
    main()
