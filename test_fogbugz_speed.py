import httpx
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv
import time

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def test_speed():
    client = httpx.Client(base_url=URL, timeout=60)
    
    print(f"Testing connectivity to {URL}...")
    
    start = time.time()
    try:
        resp = client.get("/api.asp", params={"cmd": "listWikis", "token": TOKEN})
        print(f"listWikis took {time.time() - start:.2f}s")
        print(f"Status: {resp.status_code}")
        # print(resp.text[:500])
    except Exception as e:
        print(f"listWikis failed: {e}")

    start = time.time()
    try:
        resp = client.get("/api.asp", params={"cmd": "search", "q": "axis:articles security", "token": TOKEN, "cols": "ixWikiPage,sHeadline"})
        print(f"Search 'axis:articles security' took {time.time() - start:.2f}s")
        # print(resp.text[:500])
    except Exception as e:
        print(f"Search failed: {e}")

test_speed()
