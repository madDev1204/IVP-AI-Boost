import httpx
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def test_search_simple():
    client = httpx.Client(base_url=URL, timeout=60)
    q = "security"
    # No columns, just default
    resp = client.get("/api.asp", params={"cmd": "search", "q": q, "token": TOKEN})
    print("--- RAW XML (q='security', default cols) ---")
    print(resp.text)

test_search_simple()
