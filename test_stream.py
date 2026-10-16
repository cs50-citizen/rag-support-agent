"""
Client-Side SSE Streaming Test Script
-------------------------------------
Simulates frontend consuming Server-Sent Events (SSE) typewriter stream.
Run before executing:
uvicorn app.main:app --port 8000
"""

import sys
import json
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/chat/stream"

def test_streaming():
    payload = {
        "query": "What is the daily meal allowance for business trips to Tier-1 cities?",
        "tenant_id": "tenant_default"
    }

    print("=" * 60)
    print(f"📡 Sending SSE stream request to backend: {API_URL}")
    print(f"❓ User Query: {payload['query']}")
    print("=" * 60)

    try:
        with httpx.stream("POST", API_URL, json=payload, timeout=60.0) as response:
            if response.status_code != 200:
                print(f"❌ Request failed with status code: {response.status_code}")
                return

            print("🤖 Assistant Live Typewriter Stream:")
            print("-" * 40)
            
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                
                raw_json = line[len("data: "):]
                try:
                    data = json.loads(raw_json)
                    event_type = data.get("event")

                    if event_type == "retrieving":
                        print(f"🔍 [{data.get('message')}]")
                    elif event_type == "token":
                        sys.stdout.write(data.get("text", ""))
                        sys.stdout.flush()
                    elif event_type == "done":
                        print("\n" + "-" * 40)
                        print("📚 Evidence References:")
                        for ref in data.get("references", []):
                            print(f"   - File: {ref['source']} (Chunk: {ref['id']}, Similarity: {ref['score']})")
                except json.JSONDecodeError:
                    continue

        print("\n" + "=" * 60)
        print("🎉 SSE Streaming Chat Test Completed Successfully!")
        print("=" * 60)

    except httpx.ConnectError:
        print(f"⚠️ Could not connect to {API_URL}. Ensure FastAPI is running on port 8000.")

if __name__ == "__main__":
    test_streaming()
