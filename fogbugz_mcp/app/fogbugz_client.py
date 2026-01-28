import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import re
from html import unescape
from markdownify import markdownify as md
from bs4 import BeautifulSoup

def parse_bool(value: str) -> bool:
    return value.lower() == "true"



class FogBugzClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._article_cache: Dict[int, List[Dict[str, Any]]] = {}
        self._last_cache_time: float = 0
        self.CACHE_EXPIRY = 3600  # Cache for 1 hour


    
    def _request(self, cmd: str, **params) -> ET.Element:
        params.update({
            "cmd": cmd,
            "token": self.token,
        })

        response = httpx.get(
            f"{self.base_url}/api.asp",
            params=params,
            timeout=60,
        )

        response.raise_for_status()

        try:
            return response.text
        except ET.ParseError as e:
            raise RuntimeError("Failed to parse FogBugz XML response") from e

    # -----------------------------
    # Wikis
    # -----------------------------

    def list_wikis(self) -> List[Dict]:
        """
        Fetch and parse FogBugz wikis.
        Returns a list of active (non-deleted) wikis.
        """
        response_xml = self._request("listWikis")  # whatever your API call wrapper is
        root = ET.fromstring(response_xml)

        wikis_node = root.find("wikis")
        if wikis_node is None:
            return []

        results: List[Dict] = []

        for wiki in wikis_node.findall("wiki"):
            f_deleted = wiki.findtext("fDeleted", default="false")
            if parse_bool(f_deleted):
                continue

            results.append({
                "wiki_id": int(wiki.findtext("ixWiki")),
                "name": wiki.findtext("sWiki", default="").strip(),
                "tagline": wiki.findtext("sTagLineHTML", default="").strip(),
                "root_page_id": int(wiki.findtext("ixWikiPageRoot")),
            })

        return results

    # -----------------------------
    # Articles
    # -----------------------------

    def list_articles(self, wiki_id: int) -> List[Dict[str, Any]]:
        """
        Returns articles for a given wiki.
        Each article contains:
        - article_id: ixWikiPage (needed for view_article)
        - title: sHeadline
        """
        response_xml = self._request("listArticles", ixWiki=wiki_id)
        root = ET.fromstring(response_xml)

        articles_node = root.find("articles")
        if articles_node is None:
            return []

        articles = []
        for article in articles_node.findall("article"):
            ixWikiPage = article.findtext("ixWikiPage")
            sHeadline = article.findtext("sHeadline")

            if ixWikiPage is None or sHeadline is None:
                continue

            articles.append({
                "article_id": int(ixWikiPage),
                "title": sHeadline.strip(),
            })

        return articles

    def search_articles(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for articles across all wikis. Improved with keyword matching and caching.
        """
        import time
        results = []
        print(f"\n[SERVER] --- NEW SEARCH REQUEST ---")
        print(f"[SERVER] Query: '{query}'")
        
        # Step 1: Keywords extraction
        stopwords = {'what', 'how', 'the', 'and', 'are', 'for', 'steps', 'push', 'to', 'with', 'according', 'documentation', 'ivp'}
        keywords = [w.lower() for w in query.replace('?', '').split() if len(w) > 2 and w.lower() not in stopwords]
        if not keywords: keywords = [query.lower()]
        print(f"[SERVER] Extracted keywords for matching: {keywords}")

        # Step 2: Ensure cache is populated
        current_time = time.time()
        if not self._article_cache or (current_time - self._last_cache_time) > self.CACHE_EXPIRY:
            print("[SERVER] Article cache is empty/expired. Starting full scan...")
            self.refresh_cache()

        # Step 3: Match against local index
        seen_ids = set()
        for wiki_id, articles in self._article_cache.items():
            for art in articles:
                title_lower = art['title'].lower()
                matches = [k for k in keywords if k in title_lower]
                if matches:
                    if art['article_id'] not in seen_ids:
                        # Weighting by match count
                        results.append((len(matches), art))
                        seen_ids.add(art['article_id'])

        # Sort by relevance (number of keyword hits)
        results.sort(key=lambda x: x[0], reverse=True)
        final_results = [item[1] for item in results[:10]]
        
        print(f"[SERVER] Found {len(final_results)} matching articles in local index.")
        return final_results

    def refresh_cache(self):
        import time
        start_time = time.time()
        print("[SERVER] [INDEXING] Phase 1: Listing all documentation spaces (wikis)...")
        try:
            wikis = self.list_wikis()
            print(f"[SERVER] [INDEXING] Found {len(wikis)} wikis. Phase 2: Indexing articles...")
            
            new_cache = {}
            for i, wiki in enumerate(wikis):
                # Progress indicator every 5 wikis
                if i % 10 == 0 or i == len(wikis) - 1:
                    percent = int((i + 1) / len(wikis) * 100)
                    print(f"[SERVER] [INDEXING] Progress: {percent}% ({i+1}/{len(wikis)} wikis scanned)")
                
                try:
                    articles = self.list_articles(wiki['wiki_id'])
                    if articles:
                        new_cache[wiki['wiki_id']] = articles
                except Exception as e:
                    print(f"      - Warning: Failed to scan Wiki ID {wiki['wiki_id']}: {e}")
            
            self._article_cache = new_cache
            self._last_cache_time = time.time()
            total_articles = sum(len(a) for a in new_cache.values())
            duration = time.time() - start_time
            print(f"[SERVER] [INDEXING] SUCCESS! {total_articles} articles indexed in {duration:.1f} seconds.")
        except Exception as e:
            print(f"[SERVER] [INDEXING] FATAL ERROR during scan: {e}")



    def view_article(self, article_id: int) -> Dict:
        """
        Retrieve and parse a FogBugz wiki article.
        """
        print(f"[SERVER] Fetching content for Article ID: {article_id}")
        # Step 1: Fetch XML from API
        try:
            response_xml = self._request(
                "viewArticle",
                ixWikiPage=article_id
            )
            root = ET.fromstring(response_xml)
            page = root.find("wikipage")
            if page is None:
                print(f"[SERVER] Error: Article {article_id} not found in XML response.")
                raise RuntimeError(f"No wikipage found for article_id={article_id}")

            # Step 2: Extract title and content
            title = page.findtext("sHeadline", default="").strip()
            content_html = page.findtext("sBody", default="").strip()

            print(f"[SERVER] Article '{title}' retrieved. Length: {len(content_html)} chars.")
            
            if not content_html:
                print(f"[SERVER] Warning: Article {article_id} has empty body.")

            # Step 3: Extract revision
            # ... (rest of the logic remains same but with more logging if needed)
            revision_text = page.findtext("nRevision", default="0")
            revision = int(revision_text)

            # Step 4: Extract tags
            tags: List[str] = []
            tags_node = page.find("tags")
            if tags_node is not None:
                for tag in tags_node.findall("tag"):
                    if tag.text:
                        tags.append(tag.text.strip())

            # Step 5: Convert HTML tables to Markdown
            soup = BeautifulSoup(content_html, "html.parser")
            
            # (Table conversion logic)
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                md_table = []
                for i, row in enumerate(rows):
                    cols = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
                    md_row = "| " + " | ".join(cols) + " |"
                    md_table.append(md_row)
                    if i == 0:
                        md_table.append("| " + " | ".join(["---"] * len(cols)) + " |")
                table.replace_with("\n".join(md_table))

            # Step 6: Convert HTML to Markdown
            content_md = md(str(soup), heading_style="ATX")
            
            # Step 7: Final cleanup
            content_md = re.sub(r'\n{3,}', '\n\n', content_md)

            print(f"[SERVER] Successfully parsed article {article_id} to Markdown.")
            return {
                "article_id": article_id,
                "title": title,
                "content": content_md,
                "revision": revision,
                "tags": tags,
            }
        except Exception as e:
            print(f"[SERVER] Error viewing article {article_id}: {e}")
            raise

    def refresh_cache(self):
        import time
        print("[SERVER] Fetching all wikis and articles for local indexing...")
        new_cache = {}
        try:
            wikis = self.list_wikis()
            print(f"[SERVER] Scanning {len(wikis)} wikis...")
            for wiki in wikis:
                articles = self.list_articles(wiki['wiki_id'])
                if articles:
                    new_cache[wiki['wiki_id']] = articles
            self._article_cache = new_cache
            self._last_cache_time = time.time()
            total_articles = sum(len(a) for a in new_cache.values())
            print(f"[SERVER] Indexed {total_articles} articles successfully.")
        except Exception as e:
            print(f"[SERVER] Cache refresh failed: {e}")


