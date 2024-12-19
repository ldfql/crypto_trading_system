import logging
import jieba
import asyncio
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import aiohttp
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class ChineseScraper(BaseScraper):
    """Scraper for Chinese social media platforms."""

    def __init__(self, config: Dict = None):
        super().__init__(config or {})
        self.platforms = {
            'weibo': 'https://weibo.com',
            'zhihu': 'https://www.zhihu.com',
            'xiaohongshu': 'https://www.xiaohongshu.com'
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def scrape_platform(self, platform: str, keywords: List[str]) -> List[Dict]:
        """Scrape content from specified Chinese platform."""
        try:
            if platform not in self.platforms:
                raise ValueError(f"Unsupported platform: {platform}")

            async with aiohttp.ClientSession(headers=self.headers) as session:
                results = []
                for keyword in keywords:
                    url = self._build_search_url(platform, keyword)
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            parsed_content = self._parse_content(platform, content)
                            results.extend(parsed_content)

                return results
        except Exception as e:
            logger.error(f"Error scraping {platform}: {str(e)}")
            return []

    def _build_search_url(self, platform: str, keyword: str) -> str:
        """Build search URL for different platforms."""
        base_url = self.platforms[platform]
        if platform == 'weibo':
            return f"{base_url}/search?q={keyword}"
        elif platform == 'zhihu':
            return f"{base_url}/search?type=content&q={keyword}"
        elif platform == 'xiaohongshu':
            return f"{base_url}/search_result?keyword={keyword}"
        return base_url

    def _parse_content(self, platform: str, content: str) -> List[Dict]:
        """Parse scraped content based on platform."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            results = []

            if platform == 'weibo':
                results = self._parse_weibo(soup)
            elif platform == 'zhihu':
                results = self._parse_zhihu(soup)
            elif platform == 'xiaohongshu':
                results = self._parse_xiaohongshu(soup)

            return results
        except Exception as e:
            logger.error(f"Error parsing {platform} content: {str(e)}")
            return []

    def _parse_weibo(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Weibo content."""
        posts = []
        for post in soup.find_all('div', class_='card-wrap'):
            try:
                content = post.find('p', class_='txt')
                if content:
                    posts.append({
                        'platform': 'weibo',
                        'content': content.text.strip(),
                        'timestamp': datetime.now().isoformat(),
                        'type': 'post'
                    })
            except Exception as e:
                logger.error(f"Error parsing Weibo post: {str(e)}")
        return posts

    def _parse_zhihu(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Zhihu content."""
        posts = []
        for post in soup.find_all('div', class_='List-item'):
            try:
                content = post.find('span', class_='RichText')
                if content:
                    posts.append({
                        'platform': 'zhihu',
                        'content': content.text.strip(),
                        'timestamp': datetime.now().isoformat(),
                        'type': 'answer'
                    })
            except Exception as e:
                logger.error(f"Error parsing Zhihu post: {str(e)}")
        return posts

    def _parse_xiaohongshu(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Xiaohongshu content."""
        posts = []
        for post in soup.find_all('div', class_='note-item'):
            try:
                content = post.find('div', class_='content')
                if content:
                    posts.append({
                        'platform': 'xiaohongshu',
                        'content': content.text.strip(),
                        'timestamp': datetime.now().isoformat(),
                        'type': 'note'
                    })
            except Exception as e:
                logger.error(f"Error parsing Xiaohongshu post: {str(e)}")
        return posts

    async def analyze_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Analyze sentiment of Chinese text using BERT model.
        Returns:
            Tuple[float, float]: (sentiment_score, confidence_score)
            - sentiment_score: ranges from -1 (bearish) to 1 (bullish)
            - confidence_score: ranges from 0 to 1
        """
        try:
            # Initialize sentiment analyzer if not already initialized
            if not hasattr(self, 'sentiment_analyzer'):
                from .sentiment_analyzer import SentimentAnalyzer
                self.sentiment_analyzer = SentimentAnalyzer(language='chinese')

            # Chinese-specific sentiment indicators with weights
            sentiment_indicators = {
                'bullish': {
                    '牛市': 1.2, '突破': 1.1, '上涨': 0.9, '买入': 0.9,
                    '看多': 1.0, '支撑': 0.7, '建仓': 0.9, '强势': 0.8,
                    '反弹': 0.7, '底部': 0.8, '积累': 0.7, '上升': 0.8
                },
                'bearish': {
                    '熊市': 1.2, '下跌': 1.1, '抛售': 0.9, '卖出': 0.9,
                    '看空': 1.0, '阻力': 0.7, '清仓': 0.9, '弱势': 0.8,
                    '回调': 0.7, '顶部': 0.8, '抛压': 0.7, '下降': 0.8
                }
            }

            # Calculate weighted sentiment scores
            bullish_score = sum(
                sentiment_indicators['bullish'].get(word, 0)
                for word in jieba.cut(text)
                if word in sentiment_indicators['bullish']
            )
            bearish_score = sum(
                sentiment_indicators['bearish'].get(word, 0)
                for word in jieba.cut(text)
                if word in sentiment_indicators['bearish']
            )

            # Get base sentiment from BERT model with debug logging
            base_sentiment, base_confidence = await self.sentiment_analyzer.analyze_text(text)
            logger.info(f"Base BERT sentiment: {base_sentiment}, confidence: {base_confidence}")

            # Combine BERT and keyword-based sentiment with debug logging
            if bullish_score > bearish_score:
                logger.info(f"Bullish signal detected. Scores - Bullish: {bullish_score}, Bearish: {bearish_score}")
                # Scale down the keyword influence and cap the maximum boost
                keyword_boost = min(0.2, (bullish_score - bearish_score) * 0.1)
                sentiment = min(0.8, base_sentiment + keyword_boost)
            elif bearish_score > bullish_score:
                logger.info(f"Bearish signal detected. Scores - Bullish: {bullish_score}, Bearish: {bearish_score}")
                # Scale down the keyword influence and cap the minimum boost
                keyword_boost = min(0.2, (bearish_score - bullish_score) * 0.1)
                sentiment = max(-0.8, base_sentiment - keyword_boost)
            else:
                logger.info(f"Neutral signal. Equal scores - Bullish: {bullish_score}, Bearish: {bearish_score}")
                sentiment = base_sentiment

            # Calculate final confidence score with improved weighting
            keyword_confidence = min(0.8, (bullish_score + bearish_score) / 3.0)
            logger.info(f"Keyword confidence: {keyword_confidence}")

            # Weight BERT confidence more heavily for better accuracy
            bert_weight = 0.7
            keyword_weight = 0.3
            confidence = min(0.95, bert_weight * base_confidence + keyword_weight * keyword_confidence)

            # Apply moderate confidence boost for clear signals
            if abs(sentiment) > 0.6:
                confidence = min(0.95, confidence * 1.1)

            logger.info(f"Chinese sentiment analysis complete. Score: {sentiment}, confidence: {confidence}")
            return sentiment, confidence

        except Exception as e:
            logger.error(f"Error analyzing Chinese sentiment: {str(e)}")
            raise
