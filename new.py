from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Models available for your API key:")
for model in client.models.list():
    # This prints models that support the 'generateContent' action
    if 'generateContent' in model.supported_actions:
        print(model.name)