import httpx
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def check_count():
    client = httpx.Client(base_url=URL, timeout=60)
    resp = client.get("/api.asp", params={"cmd": "listWikis", "token": TOKEN})
    root = ET.fromstring(resp.text)
    wikis = root.find("wikis")
    if wikis is not None:
        print(f"Total Wikis: {len(wikis.findall('wiki'))}")
    else:
        print("No wikis found.")

check_count()
