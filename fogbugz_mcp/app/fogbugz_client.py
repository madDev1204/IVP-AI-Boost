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

    
    def _request(self, cmd: str, **params) -> ET.Element:
        params.update({
            "cmd": cmd,
            "token": self.token,
        })

        response = httpx.get(
            f"{self.base_url}/api.asp",
            params=params,
            timeout=20,
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


    def view_article(self, article_id: int) -> Dict:
        """
        Retrieve and parse a FogBugz wiki article.
        Handles complex HTML content, code snippets, tables, and returns LLM-friendly Markdown.

        Args:
            article_id (int): The ID of the wiki article.

        Returns:
            Dict: Parsed article with keys:
                - article_id
                - title
                - content (LLM-friendly Markdown, including tables and code snippets)
                - revision
                - tags
        """
        # Step 1: Fetch XML from API
        response_xml = self._request(
            "viewArticle",
            ixWikiPage=article_id
        )
        root = ET.fromstring(response_xml)
        page = root.find("wikipage")
        if page is None:
            raise RuntimeError(f"No wikipage found for article_id={article_id}")

        # Step 2: Extract title and content
        title = page.findtext("sHeadline", default="").strip()
        content_html = page.findtext("sBody", default="").strip()

        # Step 3: Extract revision
        revision_text = page.findtext("nRevision", default="0")
        revision = int(revision_text)

        # Step 4: Extract tags
        tags: List[str] = []
        tags_node = page.find("tags")
        if tags_node is not None:
            for tag in tags_node.findall("tag"):
                if tag.text:
                    tags.append(tag.text.strip())

        # Step 5: Convert HTML tables to Markdown manually for better control
        soup = BeautifulSoup(content_html, "html.parser")

        # Convert all <table> to markdown
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            md_table = []
            for i, row in enumerate(rows):
                cols = [col.get_text(strip=True) for col in row.find_all(["th", "td"])]
                md_row = "| " + " | ".join(cols) + " |"
                md_table.append(md_row)
                if i == 0:
                    # header separator
                    md_table.append("| " + " | ".join(["---"] * len(cols)) + " |")
            table.replace_with("\n".join(md_table))

        # Step 6: Convert HTML to Markdown
        content_md = md(str(soup), heading_style="ATX")

        # Step 7: Extract code snippets from <input plugin_type="codesnippet">
        code_blocks = re.findall(r'sContent=&quot;(.*?)&quot;', content_html)
        cleaned_code_blocks = [unescape(cb).replace(r'\r\n', '\n') for cb in code_blocks]

        for cb in cleaned_code_blocks:
            language = "csharp" if re.search(r'\bclass\b|\bvar\b|client =', cb) else "json"
            content_md += f"\n\n```{language}\n{cb}\n```"

        # Step 8: Clean multiple blank lines
        content_md = re.sub(r'\n{3,}', '\n\n', content_md)

        return {
            "article_id": article_id,
            "title": title,
            # "content_html": content_html,
            "content": content_md,  # LLM-friendly Markdown
            "revision": revision,
            "tags": tags,
        }

