import httpx
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def test_cols():
    client = httpx.Client(base_url=URL, timeout=60)
    q = "security"
    # Try searching for everything to see the column structure
    resp = client.get("/api.asp", params={"cmd": "search", "q": q, "token": TOKEN, "cols": "ixBug,sTitle,ixWikiPage"})
    print("--- RAW XML (q='security') ---")
    print(resp.text)

test_cols()
