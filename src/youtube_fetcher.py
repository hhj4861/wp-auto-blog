"""YouTube Fetcher module for K-Pop content.

Fetches YouTube video thumbnails and embeds for K-Pop content.
This is the ONLY approved image source for K-Pop (copyright safety).

K-Pop agencies actively enforce copyright on artist images.
YouTube thumbnails are safe because:
1. They're official uploads or properly licensed fan content
2. Embedding is explicitly allowed by YouTube's ToS
3. Thumbnails are designed for sharing/promotion
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests
from loguru import logger


@dataclass
class YouTubeVideo:
    """Represents a YouTube video with thumbnail.

    Attributes:
        video_id: YouTube video ID
        title: Video title
        channel: Channel name
        thumbnail_url: URL to thumbnail image
        embed_url: Embeddable URL
    """

    video_id: str
    title: str
    channel: str
    thumbnail_url: str
    embed_url: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "thumbnail_url": self.thumbnail_url,
            "embed_url": self.embed_url,
        }

    def get_embed_html(self, width: int = 560, height: int = 315) -> str:
        """Generate responsive embed HTML.

        Args:
            width: Base width (used for aspect ratio)
            height: Base height (used for aspect ratio)

        Returns:
            Responsive iframe HTML
        """
        return f'''<div class="youtube-embed" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
<iframe src="{self.embed_url}"
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
    allowfullscreen>
</iframe>
</div>'''


class YouTubeFetcher:
    """Fetches YouTube video information and thumbnails.

    Example:
        >>> fetcher = YouTubeFetcher(api_key="YOUR_API_KEY")
        >>> video = fetcher.search("NewJeans Super Shy MV")
        >>> if video:
        ...     print(f"Found: {video.title}")
        ...     print(f"Thumbnail: {video.thumbnail_url}")
    """

    # Thumbnail quality options (highest to lowest)
    THUMBNAIL_QUALITIES = [
        "maxresdefault",  # 1280x720
        "sddefault",  # 640x480
        "hqdefault",  # 480x360
        "mqdefault",  # 320x180
        "default",  # 120x90
    ]

    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube fetcher.

        Args:
            api_key: YouTube Data API key (optional, uses env var if not provided)
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.session = requests.Session()

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats.

        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if invalid
        """
        if not url:
            return None

        # Direct video ID (11 characters)
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
            return url

        parsed = urlparse(url)

        # youtu.be/VIDEO_ID
        if parsed.netloc == "youtu.be":
            return parsed.path.lstrip("/")

        # youtube.com formats
        if "youtube.com" in parsed.netloc:
            # /watch?v=VIDEO_ID
            if parsed.path == "/watch":
                query = parse_qs(parsed.query)
                if "v" in query:
                    return query["v"][0]

            # /embed/VIDEO_ID or /shorts/VIDEO_ID
            if parsed.path.startswith(("/embed/", "/shorts/")):
                return parsed.path.split("/")[2]

        return None

    @staticmethod
    def get_thumbnail_url(video_id: str, quality: str = "maxresdefault") -> str:
        """Get thumbnail URL for a video.

        Args:
            video_id: YouTube video ID
            quality: Thumbnail quality (maxresdefault, sddefault, hqdefault, mqdefault, default)

        Returns:
            Thumbnail URL
        """
        return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"

    def get_best_thumbnail(self, video_id: str) -> str:
        """Get the best available thumbnail for a video.

        Tries each quality level until one is found.

        Args:
            video_id: YouTube video ID

        Returns:
            URL to the best available thumbnail
        """
        for quality in self.THUMBNAIL_QUALITIES:
            url = self.get_thumbnail_url(video_id, quality)
            try:
                response = self.session.head(url, timeout=5)
                # YouTube returns 200 even for non-existent thumbnails,
                # but content-length is tiny (< 1KB) for placeholder
                if response.status_code == 200:
                    content_length = int(response.headers.get("content-length", 0))
                    if content_length > 1000:  # Real thumbnail is > 1KB
                        return url
            except requests.RequestException:
                continue

        # Fallback to hqdefault (always exists)
        return self.get_thumbnail_url(video_id, "hqdefault")

    @staticmethod
    def get_embed_url(video_id: str) -> str:
        """Get embeddable URL for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Embed URL
        """
        return f"https://www.youtube.com/embed/{video_id}"

    def search(
        self, query: str, max_results: int = 1, video_type: str = "any"
    ) -> Optional[YouTubeVideo]:
        """Search YouTube for a video.

        Requires YOUTUBE_API_KEY to be set.

        Args:
            query: Search query (e.g., "NewJeans Super Shy MV")
            max_results: Maximum results to return
            video_type: Video type filter ("any", "episode", "movie")

        Returns:
            YouTubeVideo if found, None otherwise
        """
        if not self.api_key:
            logger.info("YOUTUBE_API_KEY 미설정 — 검색 페이지 스크레이프 폴백 사용")
            return self._search_scrape(query)

        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
            "videoType": video_type,
        }

        try:
            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("items"):
                logger.warning(f"No YouTube results for: {query}")
                return None

            item = data["items"][0]
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]

            logger.info(f"Found YouTube video: {snippet['title']}")
            return YouTubeVideo(
                video_id=video_id,
                title=snippet["title"],
                channel=snippet["channelTitle"],
                thumbnail_url=self.get_best_thumbnail(video_id),
                embed_url=self.get_embed_url(video_id),
            )

        except requests.RequestException as e:
            logger.error(f"YouTube API request failed: {e} — 스크레이프 폴백 시도")
            return self._search_scrape(query)
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing YouTube response: {e}")
            return None

    def _search_scrape(self, query: str) -> Optional["YouTubeVideo"]:
        """API 키/쿼터 없이 유튜브 검색 결과 페이지에서 첫 영상을 추출한다.

        키 미설정(로컬)·쿼터 소진(CI) 시에도 주제에 맞는 썸네일을 얻기 위한
        폴백. ytInitialData JSON에서 첫 videoRenderer를 정규식으로 파싱한다.
        """
        import re as _re
        from urllib.parse import quote as _quote

        url = f"https://www.youtube.com/results?search_query={_quote(query)}"
        try:
            response = self.session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"YouTube 검색 스크레이프 실패: {e}")
            return None

        match = _re.search(
            r'"videoRenderer":\{"videoId":"([A-Za-z0-9_-]{11})".*?'
            r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"',
            response.text,
            _re.S,
        )
        if not match:
            logger.warning(f"YouTube 스크레이프 결과 없음: {query}")
            return None
        import json as _json

        video_id = match.group(1)
        try:
            title = _json.loads(f'"{match.group(2)}"')
        except ValueError:
            title = match.group(2)
        channel_match = _re.search(
            r'"ownerText":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"',
            response.text[match.start():],
        )
        channel = channel_match.group(1) if channel_match else ""

        logger.info(f"YouTube 스크레이프 매칭: {title[:60]}")
        return YouTubeVideo(
            video_id=video_id,
            title=title,
            channel=channel,
            thumbnail_url=self.get_best_thumbnail(video_id),
            embed_url=self.get_embed_url(video_id),
        )

    def search_kpop(
        self,
        artist: str,
        song_title: Optional[str] = None,
        content_type: str = "MV",
    ) -> Optional[YouTubeVideo]:
        """Search for K-Pop content specifically.

        Args:
            artist: Artist name (e.g., "NewJeans", "BTS")
            song_title: Song title (optional)
            content_type: Content type ("MV", "live", "dance practice", "fancam")

        Returns:
            YouTubeVideo if found, None otherwise
        """
        # Build optimized search query
        query_parts = [artist]

        if song_title:
            query_parts.append(song_title)

        if content_type.upper() == "MV":
            query_parts.append("MV official")
        elif content_type.lower() == "live":
            query_parts.append("live performance")
        elif content_type.lower() == "dance practice":
            query_parts.append("dance practice")
        elif content_type.lower() == "fancam":
            query_parts.append("fancam 직캠")

        query = " ".join(query_parts)
        return self.search(query)

    def get_video_from_url(self, url: str) -> Optional[YouTubeVideo]:
        """Create YouTubeVideo from a URL without API call.

        Useful when you already have the video URL but need thumbnail info.

        Args:
            url: YouTube video URL

        Returns:
            YouTubeVideo if valid URL, None otherwise
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.warning(f"Invalid YouTube URL: {url}")
            return None

        return YouTubeVideo(
            video_id=video_id,
            title="",  # Unknown without API
            channel="",  # Unknown without API
            thumbnail_url=self.get_best_thumbnail(video_id),
            embed_url=self.get_embed_url(video_id),
        )

    def search_multiple(
        self, queries: list[str], max_per_query: int = 1
    ) -> list[YouTubeVideo]:
        """Search for multiple videos.

        Args:
            queries: List of search queries
            max_per_query: Max results per query

        Returns:
            List of YouTubeVideo objects
        """
        results = []
        seen_ids = set()
        for query in queries:
            video = self.search(query, max_results=max_per_query)
            if video and video.video_id not in seen_ids:
                results.append(video)
                seen_ids.add(video.video_id)
        return results

    def search_kfashion(
        self,
        topic: str,
        content_type: str = "style",
    ) -> Optional[YouTubeVideo]:
        """Search for K-Fashion content on YouTube.

        Args:
            topic: Fashion topic (e.g., "minimalist fashion", "seoul street style")
            content_type: Content type ("style", "haul", "lookbook", "vlog")

        Returns:
            YouTubeVideo if found, None otherwise
        """
        # Build optimized search query for K-Fashion
        query_parts = ["korean"]

        if "minimalist" in topic.lower():
            query_parts.append("minimalist fashion")
        elif "street" in topic.lower():
            query_parts.append("street style seoul")
        else:
            query_parts.append(topic)

        if content_type.lower() == "haul":
            query_parts.append("haul try on")
        elif content_type.lower() == "lookbook":
            query_parts.append("lookbook outfit")
        elif content_type.lower() == "vlog":
            query_parts.append("fashion vlog")
        else:
            query_parts.append("style guide")

        query = " ".join(query_parts)
        return self.search(query)

    def search_for_section(
        self,
        section_title: str,
        category: str,
        exclude_ids: Optional[set[str]] = None,
        topic: str = "",
    ) -> Optional[YouTubeVideo]:
        """Search YouTube for section-relevant video based on H2 title.

        Args:
            section_title: H2 section title
            category: K-Culture category (K-Pop, K-Fashion)
            exclude_ids: Video IDs to exclude (already used)
            topic: Original topic for context (artist extraction)

        Returns:
            YouTubeVideo if found, None otherwise
        """
        exclude_ids = exclude_ids or set()
        section_lower = section_title.lower()

        # Extract artist from topic for better query context
        topic_artist = self._extract_artist_from_topic(topic) if topic else ""

        # Generate search query based on section content and category
        if category == "K-Pop":
            # K-Pop specific query generation with artist context
            query = self._generate_kpop_query(section_lower, topic_artist)
        elif category == "K-Fashion":
            # K-Fashion specific query generation
            query = self._generate_kfashion_query(section_lower)
        else:
            query = f"korean {section_title[:50]}"

        logger.debug(f"YouTube section query: '{query}' (artist: {topic_artist or 'none'})")

        # Search and filter out already used videos
        if not self.api_key:
            logger.warning("YOUTUBE_API_KEY not set")
            return None

        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5,  # Get more to filter
            "key": self.api_key,
        }

        try:
            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                if video_id in exclude_ids:
                    continue

                snippet = item["snippet"]
                logger.info(f"Found YouTube video for section: {snippet['title'][:40]}...")

                return YouTubeVideo(
                    video_id=video_id,
                    title=snippet["title"],
                    channel=snippet["channelTitle"],
                    thumbnail_url=self.get_best_thumbnail(video_id),
                    embed_url=self.get_embed_url(video_id),
                )

            return None

        except Exception as e:
            logger.error(f"YouTube section search failed: {e}")
            return None

    def _extract_artist_from_topic(self, topic: str) -> str:
        """Extract K-Pop artist name from topic.

        Args:
            topic: Topic string (e.g., "BLACKPINK World Tour 2025")

        Returns:
            Artist name if found, empty string otherwise
        """
        topic_lower = topic.lower()
        kpop_artists = [
            "blackpink", "bts", "newjeans", "aespa", "twice", "stray kids",
            "seventeen", "ive", "le sserafim", "nct", "exo", "red velvet",
            "itzy", "txt", "enhypen", "ateez", "gidle", "(g)i-dle", "g idle",
            "nmixx", "illit", "riize", "zerobaseone", "boynextdoor", "xikers",
        ]
        for artist in kpop_artists:
            if artist in topic_lower:
                return artist
        return ""

    def _generate_kpop_query(self, section_lower: str, topic_artist: str = "") -> str:
        """Generate K-Pop search query from section title.

        Args:
            section_lower: Lowercase section title
            topic_artist: Artist name extracted from topic (optional)
        """
        # Extract artist names if present in section
        kpop_artists = [
            "blackpink", "bts", "newjeans", "aespa", "twice", "stray kids",
            "seventeen", "ive", "le sserafim", "nct", "exo", "red velvet",
            "itzy", "txt", "enhypen", "ateez", "gidle", "(g)i-dle",
        ]

        artist_found = topic_artist.lower() if topic_artist else None
        if not artist_found:
            for artist in kpop_artists:
                if artist in section_lower:
                    artist_found = artist
                    break

        # Keyword-based query generation with artist context
        if "setlist" in section_lower:
            if artist_found:
                return f"{artist_found} concert setlist live performance stage"
            return "kpop concert setlist live stage performance"
        elif "concert" in section_lower or "tour" in section_lower or "overview" in section_lower:
            if artist_found:
                return f"{artist_found} world tour concert stadium"
            return "kpop concert stadium arena stage"
        elif "ticket" in section_lower or "price" in section_lower or "pricing" in section_lower:
            if artist_found:
                return f"{artist_found} concert ticket stadium venue"
            return "kpop concert ticket stadium venue seats"
        elif "vip" in section_lower or "exclusive" in section_lower or "package" in section_lower:
            if artist_found:
                return f"{artist_found} vip concert experience fan meeting"
            return "kpop vip concert fan meeting backstage"
        elif "merch" in section_lower or "lightstick" in section_lower:
            if artist_found:
                return f"{artist_found} lightstick official merchandise"
            return "kpop lightstick collection official merchandise"
        elif "album" in section_lower:
            if artist_found:
                return f"{artist_found} album unboxing official"
            return "kpop album unboxing collection"
        elif "mv" in section_lower or "music video" in section_lower:
            if artist_found:
                return f"{artist_found} MV official music video"
            return "kpop official music video mv"
        elif "dance" in section_lower or "choreography" in section_lower:
            if artist_found:
                return f"{artist_found} dance practice choreography"
            return "kpop dance practice mirrored choreography"
        elif "fan" in section_lower or "fandom" in section_lower:
            if artist_found:
                return f"{artist_found} fan meeting fansign event"
            return "kpop fan meeting fansign event"
        else:
            if artist_found:
                return f"{artist_found} official performance stage"
            return "kpop idol official performance stage"

    def _generate_kfashion_query(self, section_lower: str) -> str:
        """Generate K-Fashion search query from section title."""
        # Keyword-based query generation
        if "minimalist" in section_lower:
            return "korean minimalist fashion lookbook"
        elif "street" in section_lower or "streetwear" in section_lower:
            return "seoul street fashion style"
        elif "wardrobe" in section_lower or "essential" in section_lower:
            return "korean fashion haul wardrobe essentials"
        elif "brand" in section_lower:
            return "korean fashion brand review musinsa"
        elif "sizing" in section_lower or "size" in section_lower:
            return "korean clothing size guide try on"
        elif "winter" in section_lower:
            return "korean winter fashion outfit"
        elif "summer" in section_lower:
            return "korean summer fashion lookbook"
        elif "outfit" in section_lower:
            return "korean outfit ideas ootd"
        elif "shopping" in section_lower or "buy" in section_lower:
            return "korean fashion haul shopping"
        else:
            return "korean fashion style vlog seoul"


def generate_youtube_credit(video: YouTubeVideo) -> str:
    """Generate image credit HTML for YouTube thumbnail.

    Args:
        video: YouTubeVideo object

    Returns:
        HTML string for image credit
    """
    channel_text = f" - {video.channel}" if video.channel else ""
    return f'<p class="image-credit" style="font-size: 12px; color: #888; margin-top: 4px;">Image: YouTube{channel_text}</p>'


# Convenience functions for common K-Pop content types
def search_mv(artist: str, song: str, api_key: Optional[str] = None) -> Optional[YouTubeVideo]:
    """Quick search for K-Pop music video.

    Args:
        artist: Artist name
        song: Song title
        api_key: Optional API key

    Returns:
        YouTubeVideo if found
    """
    fetcher = YouTubeFetcher(api_key=api_key)
    return fetcher.search_kpop(artist, song, content_type="MV")


def search_live(artist: str, song: str, api_key: Optional[str] = None) -> Optional[YouTubeVideo]:
    """Quick search for K-Pop live performance.

    Args:
        artist: Artist name
        song: Song title
        api_key: Optional API key

    Returns:
        YouTubeVideo if found
    """
    fetcher = YouTubeFetcher(api_key=api_key)
    return fetcher.search_kpop(artist, song, content_type="live")
