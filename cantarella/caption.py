import re

from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db

# ======================================================
# /set_caption - Set Custom Caption
# ======================================================
@Client.on_message(filters.command("set_caption") & filters.private)
async def set_caption(client: Client, message: Message):
    user_id = message.from_user.id

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)

    if len(message.command) < 2:
        return await message.reply_text(
            "<b>⚠️ Usage Error</b>\n\n"
            "Please provide the caption text after the command.\n\n"
            "<b>Correct Format:</b>\n"
            "<code>/set_caption Your Caption Here</code>\n\n"
            "<b>Supported Placeholders:</b>\n"
            "• <code>{filename}</code> : Original File Name\n"
            "• <code>{size}</code> : File Size\n\n"
            "<i>Example:</i> <code>/set_caption File: {filename} | Size: {size}</code>",
            parse_mode=enums.ParseMode.HTML
        )

    caption = message.text.split(" ", 1)[1].strip()
    await db.set_caption(user_id, caption)

    await message.reply_text(
        "<b>✅ Custom Caption Saved!</b>\n\n"
        f"<b>Preview:</b>\n<code>{caption}</code>\n\n"
        "<i>This caption will be applied to your future downloads.</i>",
        parse_mode=enums.ParseMode.HTML
    )

# ======================================================
# /see_caption - View Current Caption
# ======================================================
@Client.on_message(filters.command("see_caption") & filters.private)
async def see_caption(client: Client, message: Message):
    user_id = message.from_user.id

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)

    caption = await db.get_caption(user_id)

    if caption:
        await message.reply_text(
            "<b>📝 Your Custom Caption</b>\n\n"
            f"<code>{caption}</code>\n\n"
            "<i>To delete this, use /del_caption</i>",
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await message.reply_text(
            "<b>❌ No Caption Set</b>\n\n"
            "You are currently using the default bot caption.\n"
            "<i>Use /set_caption to customize it.</i>",
            parse_mode=enums.ParseMode.HTML
        )

# ======================================================
# /del_caption - Delete Custom Caption
# ======================================================
@Client.on_message(filters.command("del_caption") & filters.private)
async def del_caption(client: Client, message: Message):
    user_id = message.from_user.id

    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, message.from_user.first_name)

    caption = await db.get_caption(user_id)

    if not caption:
        return await message.reply_text(
            "<b>⚠️ No Caption Found</b>\n\n"
            "You don't have a custom caption set.",
            parse_mode=enums.ParseMode.HTML
        )

    await db.del_caption(user_id)
    await db.set_caption_style(user_id, None)

    await message.reply_text(
        "<b>🗑 Custom Caption Removed</b>\n\n"
        "<i>Your uploads will now use the default bot caption.</i>",
        parse_mode=enums.ParseMode.HTML
    )


# ======================================================
# Metadata extraction for caption variables
# ({title}, {quality}, {resolution}, {year}, {season}, {episode},
# {audio}, {lib}, {ott}, {fps}, {bitrate}, {language}, {shortsub}...)
# parsed from the file name / original caption via regex, plus direct
# fields that come from Telegram media attributes.
# ======================================================

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


# ======================================================
# Caption Settings UI (buttons): variables list, edit/show/delete,
# and the caption style picker.
# ======================================================

# Per-user state: waiting for the user to type a new caption template.
CAPTION_EDIT_STATE = set()

VARIABLES_TXT = (
    "<b>📝 Caption Settings</b>\n\n"
    "You can set your custom caption here using below variables.\n\n"
    "<b>📚 Variables:</b>\n"
    "<code>{file_name}</code> - Original filename\n"
    "<code>{default_caption}</code> - Original caption\n"
    "<code>{title}</code> - Title (before Year/S/L/R/Q)\n"
    "<code>{file_size}</code> - File size\n"
    "<code>{duration}</code> - Video Duration\n"
    "<code>{language}</code> - Language From Caption\n"
    "<code>{audio}</code> - Audio Type (DDP5.1, AAC2.0)\n"
    "<code>{quality}</code> - Quality (HdRip, BluRay)\n"
    "<code>{resolution}</code> - Res (480p, 1080p)\n"
    "<code>{year}</code> - Year from caption\n"
    "<code>{season}</code> - Season (S01, S02)\n"
    "<code>{episode}</code> - Episode (E01, E02)\n"
    "<code>{ott}</code> - OTT (NF, AMZN)\n"
    "<code>{lib}</code> - Codec (x264, x265)\n"
    "<code>{extension}</code> - File ext\n"
    "<code>{fps}</code> - FPS (30FPS, 60FPS)\n"
    "<code>{bitrate}</code> - Audio Bitrate (120kbps)\n"
    "<code>{shortsub}</code> - Sub (Msub/Esub)\n"
    "<code>{height}</code> - Video Height\n"
    "<code>{width}</code> - Video Width"
)


def caption_menu_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Caption", callback_data="cap_edit_btn")],
        [InlineKeyboardButton("📋 Show Caption", callback_data="cap_show_btn"),
         InlineKeyboardButton("🗑 Delete Caption", callback_data="cap_del_btn")],
        [InlineKeyboardButton("🎨 Caption Style", callback_data="cap_style_btn")],
        [InlineKeyboardButton("⬅️ Back", callback_data="settings_back_btn")],
    ])


async def show_caption_menu(callback_query: CallbackQuery):
    await callback_query.edit_message_text(
        VARIABLES_TXT,
        reply_markup=caption_menu_buttons(),
        parse_mode=enums.ParseMode.HTML,
    )


def style_buttons(selected=None):
    rows = []
    names = list(STYLE_TAGS.keys())
    for i in range(0, len(names), 2):
        row = []
        for name in names[i:i + 2]:
            mark = "🔘" if name == selected else "⚪️"
            row.append(InlineKeyboardButton(f"{mark} {name}", callback_data=f"capstyle_{name}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="caption_btn")])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="close_btn")])
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex("^(cap_edit_btn|cap_show_btn|cap_del_btn|cap_style_btn|capstyle_.+)$"))
async def caption_ui_callbacks(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data == "cap_edit_btn":
        CAPTION_EDIT_STATE.add(user_id)
        back_close = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="caption_btn")]]
        )
        await callback_query.edit_message_text(
            "<b>✏️ Send your new custom caption now.</b>\n\n"
            "You can use the variables shown in the caption settings menu, "
            "e.g. <code>{title} [{quality} {resolution}]</code>\n\n"
            "Send /cancel to abort.",
            reply_markup=back_close,
            parse_mode=enums.ParseMode.HTML,
        )

    elif data == "cap_show_btn":
        caption = await db.get_caption(user_id)
        style = await db.get_caption_style(user_id)
        back_close = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="caption_btn")]]
        )
        if caption:
            text = (
                f"<b>📋 Your Current Caption Template</b>\n\n"
                f"<code>{caption}</code>\n\n"
                f"<b>Style:</b> {style or 'None'}"
            )
        else:
            text = "<b>❌ No custom caption set.</b>\nDefault bot caption is being used."
        await callback_query.edit_message_text(text, reply_markup=back_close, parse_mode=enums.ParseMode.HTML)

    elif data == "cap_del_btn":
        await db.del_caption(user_id)
        await db.set_caption_style(user_id, None)
        await callback_query.answer("Caption removed ✅", show_alert=True)
        await show_caption_menu(callback_query)

    elif data == "cap_style_btn":
        current = await db.get_caption_style(user_id)
        await callback_query.edit_message_text(
            "<b>✍️ Select your preferred caption style</b>\n\n"
            "Select a style below to automatically format your video captions.",
            reply_markup=style_buttons(current),
            parse_mode=enums.ParseMode.HTML,
        )

    elif data.startswith("capstyle_"):
        style_name = data[len("capstyle_"):]
        if style_name not in STYLE_TAGS:
            return await callback_query.answer("Unknown style", show_alert=True)
        await db.set_caption_style(user_id, style_name)
        await callback_query.answer(f"Style set to {style_name} ✅")
        await callback_query.edit_message_reply_markup(reply_markup=style_buttons(style_name))

    await callback_query.answer()


@Client.on_message(filters.private & filters.text & filters.create(
    lambda _, __, m: bool(m.from_user) and m.from_user.id in CAPTION_EDIT_STATE
))
async def receive_new_caption(client: Client, message: Message):
    user_id = message.from_user.id

    if message.text.strip().lower() == "/cancel":
        CAPTION_EDIT_STATE.discard(user_id)
        return await message.reply_text("❌ Caption edit cancelled.")

    caption = message.text.strip()
    await db.set_caption(user_id, caption)
    CAPTION_EDIT_STATE.discard(user_id)

    await message.reply_text(
        "<b>✅ Custom Caption Saved!</b>\n\n"
        f"<code>{caption}</code>\n\n"
        "<i>Tip: use 🎨 Caption Style from the caption menu to auto-format it.</i>",
        parse_mode=enums.ParseMode.HTML,
    )
