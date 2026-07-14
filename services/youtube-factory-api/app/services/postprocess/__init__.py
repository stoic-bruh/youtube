"""Post-Processing Engine — real media analysis for completed renders.

Sub-modules:
  ffmpeg_utils.py     — real ffmpeg/ffprobe subprocess helpers (audio/frame extraction, probing)
  scoring.py           — real Pillow-based image scoring (sharpness/brightness/dominant color)
  subtitle_formats.py  — SRT/VTT/ASS text generation from word/sentence timestamps
"""
