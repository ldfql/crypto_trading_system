from typing import List, Dict, Optional
import logging
import tweepy
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ...models.signals import TradingSignal
from .sentiment_analyzer import SentimentAnalyzer
from .account_discovery import AccountDiscovery

logger = logging.getLogger(__name__)

class EnglishPlatformScraper:
    """Scraper for English social media platforms (Twitter/X and YouTube)"""

    def __init__(
        self,
        twitter_api_key: str,
        twitter_api_secret: str,
        twitter_access_token: str,
        twitter_access_secret: str,
        youtube_api_key: str,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        account_discovery: Optional[AccountDiscovery] = None
    ):
        self.twitter_client = self._init_twitter_client(
            twitter_api_key,
            twitter_api_secret,
            twitter_access_token,
            twitter_access_secret
        )
        self.youtube_client = self._init_youtube_client(youtube_api_key)
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self.account_discovery = account_discovery or AccountDiscovery()

    def _init_twitter_client(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str
    ) -> tweepy.API:
        """Initialize Twitter API client"""
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_secret)
        return tweepy.API(auth, wait_on_rate_limit=True)

    def _init_youtube_client(self, api_key: str):
        """Initialize YouTube API client"""
        return build('youtube', 'v3', developerKey=api_key)

    async def get_twitter_insights(self, accounts: List[str]) -> List[Dict]:
        """Get trading insights from specified Twitter accounts"""
        insights = []
        try:
            for account in accounts:
                tweets = self.twitter_client.user_timeline(
                    screen_name=account,
                    count=100,
                    tweet_mode="extended"
                )
                for tweet in tweets:
                    if self._is_trading_related(tweet.full_text):
                        sentiment = await self.sentiment_analyzer.analyze_text(tweet.full_text)
                        insights.append({
                            'platform': 'twitter',
                            'author': account,
                            'content': tweet.full_text,
                            'sentiment': float(sentiment),
                            'created_at': tweet.created_at
                        })
        except Exception as e:
            logger.error(f"Error fetching Twitter insights: {str(e)}")
        return insights

    async def get_youtube_insights(self, channels: List[str]) -> List[Dict]:
        """Get trading insights from specified YouTube channels"""
        insights = []
        try:
            for channel in channels:
                # Get channel ID
                channel_response = self.youtube_client.channels().list(
                    part='id',
                    forUsername=channel
                ).execute()

                if not channel_response.get('items'):
                    continue

                channel_id = channel_response['items'][0]['id']

                # Get recent videos
                videos_response = self.youtube_client.search().list(
                    part='id,snippet',
                    channelId=channel_id,
                    order='date',
                    maxResults=50
                ).execute()

                for video in videos_response.get('items', []):
                    title = video['snippet']['title']
                    description = video['snippet']['description']

                    if self._is_trading_related(title) or self._is_trading_related(description):
                        content = f"{title}\n{description}"
                        sentiment = await self.sentiment_analyzer.analyze_text(content)
                        insights.append({
                            'platform': 'youtube',
                            'channel': channel,
                            'content': content,
                            'sentiment': float(sentiment),
                            'published_at': video['snippet']['publishedAt']
                        })
        except HttpError as e:
            logger.error(f"Error fetching YouTube insights: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in YouTube insights: {str(e)}")
        return insights

    async def discover_related_accounts(self, seed_accounts: List[str]) -> List[str]:
        """Discover related trading accounts based on seed accounts"""
        return await self.account_discovery.find_related_accounts(seed_accounts)

    def _is_trading_related(self, text: str) -> bool:
        """Check if content is trading related"""
        keywords = [
            'trading', 'crypto', 'bitcoin', 'btc', 'ethereum', 'eth',
            'market', 'price', 'analysis', 'signal', 'position',
            'long', 'short', 'buy', 'sell', 'support', 'resistance',
            'breakout', 'breakdown', 'trend', 'volume'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)
