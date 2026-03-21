"""
YouTube Info Service — Fetch video metadata (title, description, chapters/timestamps).
Uses yt-dlp for reliable extraction without API keys.
Falls back to oEmbed for basic info.
"""
import logging
import re
import requests
import json

logger = logging.getLogger(__name__)


def get_video_info(video_url: str) -> dict:
    """
    Fetch YouTube video metadata: title, description, chapters/timestamps, duration.
    Tries yt-dlp first (most reliable), then oEmbed fallback.
    """
    video_id = _extract_video_id(video_url)
    if not video_id:
        return {"title": "", "description": "", "chapters": [], "duration": 0}

    # Try yt-dlp (best quality metadata)
    info = _fetch_via_ytdlp(video_url)
    if info and info.get("title"):
        return info

    # Fallback: oEmbed for title + scrape description
    info = _fetch_via_oembed(video_id)

    return info


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if len(url) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', url):
        return url
    return ""


def _fetch_via_ytdlp(video_url: str) -> dict:
    """Use yt-dlp to get full video metadata."""
    try:
        import yt_dlp

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        title = info.get("title", "")
        description = info.get("description", "")
        duration = info.get("duration", 0)

        # Extract chapters from yt-dlp (if available)
        chapters = []
        yt_chapters = info.get("chapters", [])
        if yt_chapters:
            for ch in yt_chapters:
                chapters.append({
                    "time": ch.get("start_time", 0),
                    "title": ch.get("title", ""),
                    "end_time": ch.get("end_time", 0),
                })
        else:
            # Parse chapters from description
            chapters = _parse_timestamps(description)

        return {
            "title": title,
            "description": description[:2000],  # Limit length
            "chapters": chapters,
            "duration": duration,
            "channel": info.get("channel", info.get("uploader", "")),
            "view_count": info.get("view_count", 0),
        }

    except ImportError:
        logger.warning("yt-dlp not installed. Run: pip install yt-dlp")
        return {}
    except Exception as e:
        logger.error(f"yt-dlp extraction failed: {e}")
        return {}


def _fetch_via_oembed(video_id: str) -> dict:
    """Fallback: use YouTube oEmbed API for basic info."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        return {
            "title": data.get("title", ""),
            "description": "",
            "chapters": [],
            "duration": 0,
            "channel": data.get("author_name", ""),
            "view_count": 0,
        }
    except Exception as e:
        logger.error(f"oEmbed failed: {e}")
        return {"title": "", "description": "", "chapters": [], "duration": 0}


def _parse_timestamps(description: str) -> list:
    """
    Parse chapter timestamps from YouTube description.
    Common formats:
      0:00 Introduction
      01:23 Topic One
      1:02:30 Advanced Topic
    """
    if not description:
        return []

    chapters = []
    # Match timestamps like 0:00, 01:23, 1:02:30 followed by text
    pattern = r'^[\s]*(\d{1,2}:(?:\d{2}:)?\d{2})\s+(.+?)$'

    for line in description.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            time_str = match.group(1)
            title = match.group(2).strip()

            # Convert to seconds
            parts = time_str.split(':')
            if len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                seconds = int(parts[0]) * 60 + int(parts[1])

            chapters.append({
                "time": seconds,
                "title": title,
            })

    return chapters


def format_duration(seconds: int) -> str:
    """Format seconds into human readable duration."""
    if not seconds:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
