import httpx
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("FOGBUGZ_URL")
TOKEN = os.getenv("FOGBUGZ_TOKEN")

def test_results():
    client = httpx.Client(base_url=URL, timeout=60)
    
    q = "what is ivp?"
    refined_q = f"axis:articles {q}"
    print(f"Searching for: {refined_q}")
    
    resp = client.get("/api.asp", params={"cmd": "search", "q": refined_q, "token": TOKEN, "cols": "ixWikiPage,sHeadline"})
    root = ET.fromstring(resp.text)
    
    cases = root.find("cases")
    if cases is not None:
        count = len(cases.findall("case"))
        print(f"Found {count} cases via standard search.")
        for case in cases.findall("case"):
            print(f" - {case.findtext('sHeadline')} (ID: {case.findtext('ixWikiPage')})")
    else:
        print("No cases node found.")

test_results()
