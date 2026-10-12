from google import genai
import os
from dotenv import load_dotenv

# 1. Load the hidden environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY environment variable is not set. Please add it to your .env file.")
else:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Listing available models...\n")
    for model in client.models.list():
        print(f"Model Name: {model.name}")
        print(f"Actions: {model.supported_actions}\n")