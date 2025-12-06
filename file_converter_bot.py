import os
import subprocess
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Token from environment variable (Railway il set cheyyum)
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable not set.")

SOFFICE_PATH = "soffice"  # LibreOffice binary name (Docker image il available aakum)


def convert_with_libreoffice(input_path: str, target_ext: str) -> str:
    input_path = Path(input_path)
    output_dir = input_path.parent

    cmd = [
        SOFFICE_PATH,
        "--headless",
        "--convert-to",
        target_ext,
        "--outdir",
        str(output_dir),
        str(input_path),
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice failed: {result.stderr}")

    output_file = output_dir / f"{input_path.stem}.{target_ext}"
    if not output_file.exists():
        raise FileNotFoundError("Converted file not found.")

    return str(output_file)


def convert_video_to_mp3(input_path: str) -> str:
    from moviepy.editor import VideoFileClip

    input_path = Path(input_path)
    output_file = input_path.with_suffix(".mp3")

    clip = VideoFileClip(str(input_path))
    audio = clip.audio
    if audio is None:
        raise RuntimeError("No audio track found in video.")
    audio.write_audiofile(str(output_file))
    clip.close()
    audio.close()

    return str(output_file)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📁 *File Converter Bot*\n\n"
        "First select *output format*:\n"
        "• `/topdf`  → Convert to PDF\n"
        "• `/todoc`  → Convert to DOCX\n"
        "• `/toppt`  → Convert to PPTX\n"
        "• `/tomp3`  → Convert to MP3 (from video)\n\n"
        "Then send the file *as Document*.\n"
        "_Supported combos:_\n"
        "- DOC/DOCX → PDF / PPTX\n"
        "- PPT/PPTX → PDF / PPTX\n"
        "- PDF → DOCX / PPTX\n"
        "- MP4/MKV/MOV → MP3"
    )
    await update.message.reply_markdown(msg)


async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str, label: str):
    context.user_data["target_format"] = target
    await update.message.reply_text(
        f"✅ Ok, ippo nee ayakkunna files `{label}` aayi convert cheyyam."
    )


async def to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "pdf", "PDF")


async def to_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "docx", "DOCX")


async def to_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "pptx", "PPTX")


async def to_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "mp3", "MP3")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return

    doc = update.message.document
    tg_file = await doc.get_file()
    file_name = doc.file_name or "file"

    os.makedirs("downloads", exist_ok=True)
    download_path = Path("downloads") / file_name
    await tg_file.download_to_drive(str(download_path))

    target = context.user_data.get("target_format")
    if not target:
        await update.message.reply_text(
            "⚠️ First select output format:\n"
            "Use /topdf, /todoc, /toppt, or /tomp3, then send the file again."
        )
        return

    ext = download_path.suffix.lower().lstrip(".")

    try:
        if target == "pdf":
            if ext in ("doc", "docx", "ppt", "pptx"):
                out_path = convert_with_libreoffice(str(download_path), "pdf")
            else:
                raise ValueError("PDF conversion supports only DOC/DOCX/PPT/PPTX → PDF.")

        elif target == "docx":
            if ext in ("pdf", "doc", "docx"):
                out_path = convert_with_libreoffice(str(download_path), "docx")
            else:
                raise ValueError("DOCX output supports PDF/DOC/DOCX as input.")

        elif target == "pptx":
            if ext in ("pdf", "ppt", "pptx", "doc", "docx"):
                out_path = convert_with_libreoffice(str(download_path), "pptx")
            else:
                raise ValueError("PPTX output supports PDF/PPT/PPTX/DOC/DOCX as input.")

        elif target == "mp3":
            if ext in ("mp4", "mkv", "mov"):
                out_path = convert_video_to_mp3(str(download_path))
            else:
                raise ValueError("MP3 output supports MP4/MKV/MOV video files.")

        else:
            raise ValueError("Unknown target format.")

        with open(out_path, "rb") as f:
            await update.message.reply_document(
                f, filename=Path(out_path).name
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Conversion failed: {e}")
    finally:
        try:
            if download_path.exists():
                os.remove(download_path)
        except Exception:
            pass


async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("topdf", to_pdf))
    app.add_handler(CommandHandler("todoc", to_doc))
    app.add_handler(CommandHandler("toppt", to_ppt))
    app.add_handler(CommandHandler("tomp3", to_mp3))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("🤖 Bot running...")
    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
