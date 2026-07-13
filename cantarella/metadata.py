# Extracts caption variables ({title}, {quality}, {resolution}, {year}, ...)
# from a file name / original caption using regex, plus direct fields that
# come from Telegram media attributes (duration, size, height, width...).

import re

QUALITY_RE = re.compile(r"(?i)\b(HDRip|HDCAM|CAMRip|DVDRip|BluRay|BDRip|WEB[- ]?DL|WEBRip|HDTV|PreDVD|HDTS)\b")
RESOLUTION_RE = re.compile(r"(?i)\b(4K|2160p|1080p|720p|480p|360p|240p)\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
SEASON_RE = re.compile(r"(?i)\bS(\d{1,2})(?:[EX]|\b)")
EPISODE_RE = re.compile(r"(?i)\bS\d{1,2}[.\s_-]?E(\d{1,3})\b")
OTT_RE = re.compile(r"(?i)\b(NF|AMZN|HS|ZEE5|SONYLIV|DSNP|ATVP|ALTBALAJI|ALTB|HOTSTAR|JIOCINEMA)\b")
CODEC_RE = re.compile(r"(?i)\b(x264|x265|H\.?264|H\.?265|HEVC|AVC)\b")
AUDIO_RE = re.compile(r"(?i)\b(DDP?5\.1|DDP?2\.0|DD5\.1|DD2\.0|AAC5\.1|AAC2\.0|AAC|AC3|DTS|ATMOS)\b")
FPS_RE = re.compile(r"(?i)\b(\d{2,3})\s?FPS\b")
BITRATE_RE = re.compile(r"(?i)\b(\d{2,4})\s?kbps\b")
LANGUAGE_RE = re.compile(r"(?i)\b(Hindi|English|Tamil|Telugu|Kannada|Malayalam|Bengali|Marathi|Punjabi|Multi[- ]?Audio|Dual[- ]?Audio|Multi|Dual)\b")
SUB_RE = re.compile(r"(?i)\b(MultiSub|Msub|Esub|Dsub)\b")


def humanbytes(size):
    if not size:
        return "0B"
    power = 2 ** 10
    n = 0
    dic_power = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {dic_power[n]}B"


def format_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _extract_title(name, cut_positions):
    if not cut_positions:
        title = name
    else:
        title = name[: min(cut_positions)]
    title = re.sub(r"[._]+", " ", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -._")
    return title


def extract_metadata(msg, file_name, file_size=0, duration=0, height=0, width=0):
    """Build the dict of variables used in custom caption templates."""
    default_caption = getattr(msg, "caption", None)
    default_caption = default_caption.__str__() if default_caption else ""
    search_text = f"{file_name} {default_caption}"

    name_no_ext = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    extension = file_name.rsplit(".", 1)[-1] if "." in file_name else ""

    quality_m = QUALITY_RE.search(search_text)
    resolution_m = RESOLUTION_RE.search(search_text)
    year_m = YEAR_RE.search(search_text)
    season_m = SEASON_RE.search(search_text)
    episode_m = EPISODE_RE.search(search_text)
    ott_m = OTT_RE.search(search_text)
    codec_m = CODEC_RE.search(search_text)
    audio_m = AUDIO_RE.search(search_text)
    fps_m = FPS_RE.search(search_text)
    bitrate_m = BITRATE_RE.search(search_text)
    language_m = LANGUAGE_RE.search(search_text)
    sub_m = SUB_RE.search(search_text)

    cut_positions = [
        m.start() for m in [
            YEAR_RE.search(name_no_ext),
            SEASON_RE.search(name_no_ext),
            QUALITY_RE.search(name_no_ext),
            RESOLUTION_RE.search(name_no_ext),
        ] if m
    ]
    title = _extract_title(name_no_ext, cut_positions)

    return {
        "file_name": file_name,
        "default_caption": default_caption,
        "title": title,
        "file_size": humanbytes(file_size),
        "duration": format_duration(duration),
        "language": language_m.group(1) if language_m else "",
        "audio": audio_m.group(1) if audio_m else "",
        "quality": quality_m.group(1) if quality_m else "",
        "resolution": resolution_m.group(1) if resolution_m else "",
        "year": year_m.group(1) if year_m else "",
        "season": f"S{int(season_m.group(1)):02d}" if season_m else "",
        "episode": f"E{int(episode_m.group(1)):02d}" if episode_m else "",
        "ott": ott_m.group(1).upper() if ott_m else "",
        "lib": codec_m.group(1) if codec_m else "",
        "extension": extension,
        "fps": f"{fps_m.group(1)}FPS" if fps_m else "",
        "bitrate": f"{bitrate_m.group(1)}kbps" if bitrate_m else "",
        "shortsub": sub_m.group(1) if sub_m else "",
        "height": str(height) if height else "",
        "width": str(width) if width else "",
    }


STYLE_TAGS = {
    "Bold": ("<b>", "</b>"),
    "Italic": ("<i>", "</i>"),
    "Mono": ("<code>", "</code>"),
    "Bold Italic": ("<b><i>", "</i></b>"),
    "Underline": ("<u>", "</u>"),
    "Strike": ("<s>", "</s>"),
    "Blockquote": ("<blockquote>", "</blockquote>"),
    "Pre": ("<pre>", "</pre>"),
}


def apply_style(text, style_name):
    if not style_name or style_name not in STYLE_TAGS or not text:
        return text
    open_tag, close_tag = STYLE_TAGS[style_name]
    return f"{open_tag}{text}{close_tag}"


def render_caption(template, variables, style_name=None):
    class SafeDict(dict):
        def __missing__(self, key):
            return ""

    try:
        text = template.format_map(SafeDict(variables))
    except Exception:
        text = template
    return apply_style(text, style_name)
