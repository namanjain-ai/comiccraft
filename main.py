from dotenv import load_dotenv
import os
import json
import io
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from google import genai
from google.genai import types

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.lib.units import mm


# ==========================================
# LOAD ENVIRONMENT
# ==========================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")


# ==========================================
# GEMINI CLIENT
# ==========================================

# Primary model — rolling alias, always valid
PRIMARY_MODEL = "gemini-flash-latest"

# Fallback models tried in order if primary is unavailable
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-lite-latest",
]

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=5,
            initial_delay=2.0,
            max_delay=30.0,
        )
    ),
)


# ==========================================
# FASTAPI
# ==========================================

app = FastAPI(title="ComicCraft - AI Comic Story Creator")

templates = Jinja2Templates(directory="templates")


# ==========================================
# REQUEST MODELS
# ==========================================

class ComicRequest(BaseModel):
    idea: str


class ComicData(BaseModel):
    title: str = "Untitled Comic"
    genre: str = "Comic"
    characters: list = []
    setting: str = ""
    chapter1: dict = {}
    chapter2: dict = {}
    chapter3: dict = {}
    ending: str = ""


class PDFRequest(BaseModel):
    comic: ComicData


# ==========================================
# ESCAPE PDF TEXT
# ==========================================

def escape_pdf_text(text):
    """Escape special characters for ReportLab Paragraph."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ==========================================
# GEMINI CALL WITH RETRY + FALLBACK
# ==========================================

def call_gemini_with_fallback(prompt: str):
    """
    Try the primary model first. If it fails with 503 (busy),
    try fallback models. Return the text response.

    Raises the last exception if all attempts fail.
    """
    models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
    last_exception = None

    for model_name in models_to_try:
        try:
            print(f"[Gemini] Trying model: {model_name}")

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.9,
                    "max_output_tokens": 3000,
                },
            )

            if response and response.text:
                print(f"[Gemini] Success with model: {model_name}")
                return response.text

            print(f"[Gemini] Empty response from {model_name}, trying next...")

        except Exception as e:
            error_text = str(e)
            last_exception = e

            # 503 = service busy → try next model
            if "503" in error_text or "UNAVAILABLE" in error_text.upper():
                print(f"[Gemini] {model_name} busy (503), trying next...")
                # Small delay before trying next model
                time.sleep(1)
                continue

            # 429 = rate limit → try next model
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text.upper():
                print(f"[Gemini] {model_name} rate-limited (429), trying next...")
                time.sleep(2)
                continue

            # Other errors: re-raise immediately (auth, bad request, etc.)
            raise

    # All models failed
    if last_exception:
        raise last_exception
    raise RuntimeError("All Gemini models failed with no exception recorded.")


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


# ==========================================
# HISTORY
# ==========================================

@app.get("/history")
def history(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={},
    )


# ==========================================
# GENERATE COMIC
# ==========================================

@app.post("/generate")
def generate_comic(data: ComicRequest):
    try:
        idea = data.idea.strip()

        if not idea:
            return JSONResponse(
                status_code=400,
                content={"message": "Please enter a comic idea first."},
            )

        prompt = f"""
You are ComicCraft, an AI Comic Story Creator.

Create a complete comic storyline based on the user's idea.

USER IDEA:
{idea}

Create the story with the following information:

1. TITLE - A creative title for the comic.
2. GENRE - The genre of the comic.
3. MAIN CHARACTERS - name, personality, role for each.
4. SETTING - where and when the story takes place.
5. CHAPTER 1 - scene, actions, dialogue.
6. CHAPTER 2 - continue directly from Chapter 1.
7. CHAPTER 3 - continue directly from Chapter 2.
8. ENDING - a clear ending.

IMPORTANT RULES:
- Keep the entire story connected.
- Characters must remain consistent.
- Use natural dialogue.
- Include interesting actions and scenes.
- Make the story suitable for a general audience.
- Make it detailed enough for a college project demonstration.
- Do not mention AI or Gemini inside the story.
- Do not explain how the story was created.
- Do not leave any section empty.

VERY IMPORTANT:
Return ONLY valid JSON using EXACTLY this structure:

{{
    "title": "Comic title",
    "genre": "Comic genre",
    "characters": [
        {{
            "name": "Character name",
            "personality": "Character personality",
            "role": "Character role"
        }}
    ],
    "setting": "Story setting",
    "chapter1": {{
        "scene": "Scene description",
        "actions": "Actions happening in the scene",
        "dialogue": "Character dialogue"
    }},
    "chapter2": {{
        "scene": "Scene description",
        "actions": "Actions happening in the scene",
        "dialogue": "Character dialogue"
    }},
    "chapter3": {{
        "scene": "Scene description",
        "actions": "Actions happening in the scene",
        "dialogue": "Character dialogue"
    }},
    "ending": "Clear ending of the comic"
}}

Do not add Markdown.
Do not add ```json.
Do not add any text before or after the JSON.
"""

        # ✅ Uses retry + fallback helper
        response_text = call_gemini_with_fallback(prompt)

        try:
            comic = json.loads(response_text)
        except json.JSONDecodeError:
            print("INVALID GEMINI JSON:", response_text)
            return JSONResponse(
                status_code=500,
                content={"message": "Gemini returned an invalid story format."},
            )

        return {
            "message": "Comic story generated successfully!",
            "comic": comic,
        }

    except Exception as e:
        print("GEMINI ERROR:", repr(e))
        error_text = str(e)

        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text.upper():
            message = (
                "Gemini rate limit reached. Please wait a minute and try again."
            )

        elif "503" in error_text or "UNAVAILABLE" in error_text.upper():
            message = (
                "Gemini is temporarily busy right now. "
                "Please wait a moment and try again."
            )

        elif "404" in error_text or "NOT_FOUND" in error_text.upper():
            message = (
                "The selected Gemini model is unavailable for this API account. "
                "Please check available models."
            )

        elif (
            "API key" in error_text
            or "api_key" in error_text
            or "authentication" in error_text.lower()
            or "PERMISSION_DENIED" in error_text.upper()
        ):
            message = "Gemini API key problem. Please check your .env file."

        else:
            message = "Comic generation failed. Please check the terminal."

        return JSONResponse(
            status_code=500,
            content={"message": message, "error": error_text},
        )


# ==========================================
# DOWNLOAD PDF
# ==========================================

@app.post("/download-pdf")
def download_pdf(payload: PDFRequest):
    try:
        comic = payload.comic

        # --------------------------------------
        # PDF BUFFER
        # --------------------------------------
        buffer = io.BytesIO()

        # --------------------------------------
        # PDF DOCUMENT
        # --------------------------------------
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        # --------------------------------------
        # STYLES
        # --------------------------------------
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ComicTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6c5ce7"),
            spaceAfter=12,
        )

        genre_style = ParagraphStyle(
            "Genre",
            parent=styles["Normal"],
            fontSize=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#8e44ad"),
            spaceAfter=20,
        )

        heading_style = ParagraphStyle(
            "Heading",
            parent=styles["Heading2"],
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#6c5ce7"),
            spaceBefore=15,
            spaceAfter=8,
        )

        subheading_style = ParagraphStyle(
            "SubHeading",
            parent=styles["Heading3"],
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#8e44ad"),
            spaceBefore=10,
            spaceAfter=5,
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=16,
            spaceAfter=8,
        )

        # --------------------------------------
        # STORY CONTENT
        # --------------------------------------
        story = []

        title = comic.title or "Untitled Comic"
        genre = comic.genre or "Comic"
        setting = comic.setting or "No setting provided."
        ending = comic.ending or "No ending provided."

        # TITLE
        story.append(Paragraph("COMICCRAFT", title_style))
        story.append(Paragraph(escape_pdf_text(title), title_style))
        story.append(
            Paragraph(escape_pdf_text("Genre: " + str(genre)), genre_style)
        )
        story.append(Spacer(1, 10))

        # CHARACTERS
        story.append(Paragraph("Main Characters", heading_style))

        for character in comic.characters or []:
            name = character.get("name", "Unknown")
            personality = character.get("personality", "")
            role = character.get("role", "")

            story.append(Paragraph(escape_pdf_text(name), subheading_style))
            story.append(
                Paragraph(
                    "<b>Personality:</b> " + escape_pdf_text(personality),
                    body_style,
                )
            )
            story.append(
                Paragraph("<b>Role:</b> " + escape_pdf_text(role), body_style)
            )

        # SETTING
        story.append(Paragraph("Setting", heading_style))
        story.append(Paragraph(escape_pdf_text(setting), body_style))

        # CHAPTERS
        chapters = [
            ("Chapter 1", comic.chapter1 or {}),
            ("Chapter 2", comic.chapter2 or {}),
            ("Chapter 3", comic.chapter3 or {}),
        ]

        for chapter_name, chapter in chapters:
            story.append(PageBreak())
            story.append(Paragraph(escape_pdf_text(chapter_name), heading_style))

            scene = chapter.get("scene", "")
            actions = chapter.get("actions", "")
            dialogue = chapter.get("dialogue", "")

            story.append(Paragraph("Scene", subheading_style))
            story.append(Paragraph(escape_pdf_text(scene), body_style))

            story.append(Paragraph("Actions", subheading_style))
            story.append(Paragraph(escape_pdf_text(actions), body_style))

            story.append(Paragraph("Dialogue", subheading_style))
            story.append(Paragraph(escape_pdf_text(dialogue), body_style))

        # ENDING
        story.append(PageBreak())
        story.append(Paragraph("Ending", heading_style))
        story.append(Paragraph(escape_pdf_text(ending), body_style))

        # FOOTER
        story.append(Spacer(1, 30))
        story.append(Paragraph("Created with ComicCraft", genre_style))

        # --------------------------------------
        # BUILD PDF
        # --------------------------------------
        document.build(story)
        buffer.seek(0)
        pdf_bytes = buffer.getvalue()

        # --------------------------------------
        # FILE NAME
        # --------------------------------------
        safe_title = "".join(
            c if c.isalnum() else "_" for c in str(title)
        )
        filename = (safe_title or "ComicCraft_Story") + ".pdf"

        # --------------------------------------
        # RETURN PDF
        # --------------------------------------
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except Exception as e:
        print("PDF ERROR:", repr(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Unable to create PDF.", "error": str(e)},
        )