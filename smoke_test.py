import sys
import ai_engine
from ai_engine import client
import instructor

print("1. Checking connection...")
if ai_engine.check_connection():
    print("   Connection OK")
else:
    print("   Connection FAILED")
    sys.exit(1)

print("2. Attempting simple generation...")
try:
    resp = client.chat.completions.create(
        model=ai_engine.MODEL_NAME,
        messages=[{"role": "user", "content": "Say 'System Operational'"}],
        response_model=str
    )
    print(f"   AI Response: {resp}")
except Exception as e:
    print(f"   Generation Failed: {e}")
