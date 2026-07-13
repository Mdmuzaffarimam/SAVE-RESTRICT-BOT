from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from cantarella.metadata import STYLE_TAGS

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
