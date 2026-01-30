import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import re
from html import unescape
from markdownify import markdownify as md
from bs4 import BeautifulSoup
import time

def parse_bool(value: str) -> bool:
    return value.lower() == "true"

class FogBugzClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        # Cache: List of all known articles
        self._all_articles: List[Dict[str, Any]] = []
        self._cache_built = False

    def _request(self, cmd: str, **params) -> str:
        params.update({
            "cmd": cmd,
            "token": self.token,
        })
        # large timeout for listing all wikis/articles if needed
        response = httpx.get(
            f"{self.base_url}/api.asp",
            params=params,
            timeout=120,
        )
        response.raise_for_status()
        return response.text

    def _build_cache(self):
        """Crawls all wikis and articles to build a searchable index."""
        if self._cache_built:
            return

        print("[SERVER] [INDEXING] Starting full wiki crawl (API search is unreliable)...")
        try:
            # 1. List Wikis
            wikis = self.list_wikis()
            print(f"[SERVER] [INDEXING] Found {len(wikis)} wikis. Fetching article lists...")
            
            all_found = []
            
            # 2. List Articles for each Wiki
            # Optimization: We could use asyncio here for parallel fetching, 
            # but standard sequential is safer for avoiding rate limits/errors for now.
            for i, wiki in enumerate(wikis):
                w_id = wiki['wiki_id']
                w_name = wiki['name']
                
                try:
                    articles = self.list_articles(w_id)
                    # Tag them with wiki name for context
                    for art in articles:
                        art['wiki_name'] = w_name
                    
                    all_found.extend(articles)
                    
                    # Progress log
                    if (i + 1) % 5 == 0:
                        print(f"[SERVER] [INDEXING] Scanned {i + 1}/{len(wikis)} wikis...")
                        
                except Exception as e:
                    print(f"Error scanning wiki {w_id}: {e}")

            self._all_articles = all_found
            self._cache_built = True
            print(f"[SERVER] [INDEXING] Complete. Index contains {len(self._all_articles)} articles.")
            
        except Exception as e:
            print(f"[SERVER] [INDEXING] Fatal error: {e}")

    # -----------------------------
    # Wikis
    # -----------------------------

    def list_wikis(self) -> List[Dict]:
        response_xml = self._request("listWikis")
        root = ET.fromstring(response_xml)
        wikis_node = root.find("wikis")
        if wikis_node is None: return []

        results = []
        for wiki in wikis_node.findall("wiki"):
            f_deleted = wiki.findtext("fDeleted", default="false")
            if parse_bool(f_deleted): continue

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
        response_xml = self._request("listArticles", ixWiki=wiki_id)
        root = ET.fromstring(response_xml)
        articles_node = root.find("articles")
        if articles_node is None: return []

        articles = []
        for article in articles_node.findall("article"):
            ixWikiPage = article.findtext("ixWikiPage")
            sHeadline = article.findtext("sHeadline")
            if ixWikiPage and sHeadline:
                articles.append({
                    "article_id": int(ixWikiPage),
                    "title": sHeadline.strip(),
                })
        return articles

    def search_articles(self, query: str) -> List[Dict[str, Any]]:
        """
        Performs a local search against the cached article index.
        """
        print(f"[SERVER] Searching local index for: '{query}'")
        self._build_cache()
        
        # Simple keyword matching
        keywords = query.lower().split()
        results = []
        
        for art in self._all_articles:
            title_lower = art['title'].lower()
            # Score: how many keywords are present?
            score = sum(1 for k in keywords if k in title_lower)
            
            if score > 0:
                results.append((score, art))
        
        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Return top 15
        final_results = [r[1] for r in results[:15]]
        print(f"[SERVER] Found {len(final_results)} matches in local index.")
        return final_results

    def view_article(self, article_id: int) -> Dict:
        print(f"[SERVER] Fetching content for Article ID: {article_id}")
        try:
            response_xml = self._request("viewArticle", ixWikiPage=article_id)
            root = ET.fromstring(response_xml)
            page = root.find("wikipage")
            if page is None:
                raise RuntimeError(f"No wikipage found for article_id={article_id}")

            title = page.findtext("sHeadline", default="").strip()
            content_html = page.findtext("sBody", default="").strip()
            # Extract tags
            tags = []
            tags_node = page.find("tags")
            if tags_node:
                for tag in tags_node.findall("tag"):
                    if tag.text: tags.append(tag.text.strip())

            # Convert HTML tables to Markdown
            soup = BeautifulSoup(content_html, "html.parser")
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                md_table = []
                for i, row in enumerate(rows):
                    cols = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
                    if not cols: continue
                    md_row = "| " + " | ".join(cols) + " |"
                    md_table.append(md_row)
                    if i == 0:
                        md_table.append("| " + " | ".join(["---"] * len(cols)) + " |")
                table.replace_with("\n".join(md_table))

            content_md = md(str(soup), heading_style="ATX")
            content_md = re.sub(r'\n{3,}', '\n\n', content_md)

            return {
                "article_id": article_id,
                "title": title,
                "content": content_md,
                "tags": tags,
            }
        except Exception as e:
            print(f"[SERVER] Error viewing article {article_id}: {e}")
            raise
