from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import base64


# ==============================
# LOAD API KEY
# ==============================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found in .env file"
    )

client = genai.Client(api_key=API_KEY)


# ==============================
# ENSURE OUTPUT DIRECTORY EXISTS
# ==============================

os.makedirs(
    os.path.join("static", "images"),
    exist_ok=True
)


# ==============================
# GENERATE IMAGE
# ==============================

def generate_panel_image(prompt, filename):
    """
    Generate an image using Gemini's image generation model.

    Args:
        prompt (str): Text description of the image.
        filename (str): Output filename (e.g. "panel1.png").

    Returns:
        str | None: Path to saved image on success, None on failure.
    """

    try:

        response = client.models.generate_content(
            model="gemini-3.1-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="16:9",
                    image_size="1K",
                ),
            ),
        )

        # ------------------------------
        # EXTRACT IMAGE BYTES
        # ------------------------------

        image_bytes = None

        if (
            response
            and response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if (
                    hasattr(part, "inline_data")
                    and part.inline_data
                    and part.inline_data.data
                ):
                    # SDK may return bytes or base64 str
                    data = part.inline_data.data

                    if isinstance(data, str):
                        image_bytes = base64.b64decode(data)
                    else:
                        image_bytes = data

                    break

        if image_bytes is None:
            print("IMAGE GENERATION ERROR: no image data in response")
            return None

        # ------------------------------
        # SAVE TO DISK
        # ------------------------------

        output_path = os.path.join(
            "static",
            "images",
            filename
        )

        with open(output_path, "wb") as file:
            file.write(image_bytes)

        print(f"Image generated successfully: {output_path}")

        return output_path

    except Exception as e:

        print("IMAGE GENERATION ERROR:", repr(e))

        return None