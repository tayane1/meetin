import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Print database configuration (safely)
print("Database configuration:")
print(f"DB_NAME: {os.getenv('DB_NAME', 'Not set')}")
print(f"DB_USER: {os.getenv('DB_USER', 'Not set')}")
print(f"DB_PASSWORD: {'*' * len(os.getenv('DB_PASSWORD', '')) if os.getenv('DB_PASSWORD') else 'Not set'}")
print(f"DB_HOST: {os.getenv('DB_HOST', 'Not set')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 'Not set')}")

# Check for non-ASCII characters
password = os.getenv('DB_PASSWORD', '')
if password:
    try:
        password.encode('ascii')
        print("\n✓ Password contains only ASCII characters")
    except UnicodeEncodeError:
        print("\n✗ Password contains non-ASCII characters!")
        print("Non-ASCII character positions:")
        for i, char in enumerate(password):
            if ord(char) > 127:
                print(f"  Position {i}: {repr(char)} (code: {ord(char)})")