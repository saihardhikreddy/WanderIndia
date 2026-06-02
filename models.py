from google import genai
import os
from dotenv import load_dotenv

# 1. Load the hidden environment variables
load_dotenv()

# 2. DELETE your exposed key and replace it with this:
GCP_API_KEY = os.getenv("GEMINI_API_KEY") # (Make sure the variable name matches what you use in your code)

client = genai.Client(api_key=GEMINI_API_KEY)

print("Listing available models...\n")

for model in client.models.list():
    # We changed 'supported_methods' to 'supported_actions'
    print(f"Model Name: {model.name}")
    print(f"Actions: {model.supported_actions}\n")