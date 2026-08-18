"""Browser tools — open URLs, Google search, YouTube playback."""
import re
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


def _open_in_browser(target_url: str):
    """Helper to open URL in existing Chrome window or default browser."""
    try:
        subprocess.Popen(["google-chrome", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            subprocess.Popen(["xdg-open", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            import webbrowser
            webbrowser.open(target_url)


@tool
def open_url(url: str) -> str:
    """Opens a specified URL in the default web browser (e.g. Chrome)."""
    logger.info(f"Opening URL: {url}")
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        _open_in_browser(url)
        return f"OK:browser url={url}"
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {e}")
        return f"Failed to open URL: {e}"


@tool
def search_google(query: str) -> str:
    """Searches Google in the user's active/default browser window for the given query."""
    logger.info(f"Searching Google for: {query}")
    try:
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        _open_in_browser(url)
        return f"OK:browser url={url} query={query}"
    except Exception as e:
        logger.error(f"Failed to search Google for {query}: {e}")
        return f"Failed to search Google: {e}"


@tool
def play_youtube(query: str) -> str:
    """Searches YouTube and directly plays the top matching video in the browser."""
    logger.info(f"Playing YouTube query: {query}")
    try:
        import urllib.parse
        import urllib.request

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        html = urllib.request.urlopen(req).read().decode("utf-8")
        video_ids = re.findall(r"watch\?v=(\w{11})", html)

        if video_ids:
            direct_video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            logger.info(f"Top YouTube video found: {direct_video_url}")
            _open_in_browser(direct_video_url)
            return f"OK:youtube query={query} url={direct_video_url}"
        _open_in_browser(search_url)
        return f"OK:youtube_search query={query} url={search_url}"

    except Exception as e:
        logger.error(f"Failed to play YouTube video for {query}: {e}")
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            _open_in_browser(search_url)
            return f"OK:youtube_search query={query} url={search_url}"
        except Exception:
            return f"Failed to play YouTube video: {e}"
