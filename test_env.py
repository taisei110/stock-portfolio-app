from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path(__file__).parent / ".env"
print(f"Looking for .env at: {env_path}")
print(f"File exists: {env_path.exists()}")

# Try to read the file directly
if env_path.exists():
    print(f"\n--- .env file contents ---")
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
        print(repr(content))
    print(f"--- end of file ---\n")

# Now load with dotenv
load_dotenv(env_path)

api_key = os.getenv("GEMINI_API_KEY")
print(f"GEMINI_API_KEY value: '{api_key}'")
print(f"GEMINI_API_KEY is None: {api_key is None}")
print(f"GEMINI_API_KEY is empty string: {api_key == ''}")
