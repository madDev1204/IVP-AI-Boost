import httpx
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def test_raw():
    client = httpx.Client(base_url=URL, timeout=60)
    q = "what is ivp?"
    # Try without axis:articles first to see what we get
    resp = client.get("/api.asp", params={"cmd": "search", "q": q, "token": TOKEN, "cols": "ixWikiPage,sHeadline"})
    print("--- RAW XML (q='what is ivp?') ---")
    print(resp.text)

    resp = client.get("/api.asp", params={"cmd": "search", "q": f"axis:articles {q}", "token": TOKEN, "cols": "ixWikiPage,sHeadline"})
    print("\n--- RAW XML (q='axis:articles what is ivp?') ---")
    print(resp.text)

test_raw()
