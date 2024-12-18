from typing import List, Dict, Set
import logging
import tweepy
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    async def acquire(self):
        now = datetime.now()
        self.requests = [ts for ts in self.requests if now - ts < timedelta(seconds=self.time_window)]

        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + timedelta(seconds=self.time_window) - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self.requests.pop(0)

        self.requests.append(now)

class AccountDiscovery:
    """Discovers related trading accounts across social media platforms"""

    def __init__(
        self,
        twitter_api_key: str = None,
        twitter_api_secret: str = None,
        twitter_access_token: str = None,
        twitter_access_secret: str = None,
        youtube_api_key: str = None
    ):
        self.twitter_client = None
        self.youtube_client = None
        self.twitter_rate_limiter = RateLimiter(max_requests=180, time_window=900)  # 180 requests per 15 minutes
        self.youtube_rate_limiter = RateLimiter(max_requests=100, time_window=100)  # 100 requests per 100 seconds

        # Enhanced seed accounts including major institutions
        self.seed_accounts = {
            'twitter': [
                # Influential Individuals
                'elonmusk',        # Elon Musk
                'cz_binance',      # Binance CEO
                'VitalikButerin',  # Ethereum founder
                'SBF_FTX',         # FTX
                'aantonop',        # Andreas Antonopoulos
                'APompliano',      # Anthony Pompliano
                'michael_saylor',  # MicroStrategy CEO
                'CamiRusso',       # The Defiant founder
                'MessariCrypto',   # Ryan Selkis

                # Major Exchanges
                'binance',         # Binance
                'coinbase',        # Coinbase
                'krakenfx',        # Kraken
                'BitMEXdotcom',    # BitMEX
                'FTX_Official',    # FTX
                'kucoincom',       # KuCoin
                'HuobiGlobal',     # Huobi

                # Financial Institutions
                'Grayscale',       # Grayscale Investments
                'CoinSharesCo',    # CoinShares
                'BitfuryGroup',    # Bitfury
                'BlockFi',         # BlockFi
                'CelsiusNetwork',  # Celsius Network

                # News and Analysis
                'TheBlock__',      # The Block
                'coindesk',        # CoinDesk
                'Cointelegraph',   # Cointelegraph
                'DocumentingBTC',  # Bitcoin Archive
                'BitcoinMagazine' # Bitcoin Magazine
            ],
            'youtube': [
                'BitBoyCrypto',
                'CryptosRUs',
                'DataDash',
                'IvanOnTech',
                'CryptoDaily',
                'Altcoin Daily',
                'CoinBureau',
                'MMCrypto',
                'CryptoZombie',
                'The Modern Investor'
            ]
        }

        # Enhanced influence thresholds
        self.min_follower_count = 50000  # Increased from 1000
        self.min_engagement_rate = 0.03   # 3% engagement rate
        self.min_trading_content_ratio = 0.4  # 40% trading-related content
        self.min_verified_status = True   # Require verified status for Twitter accounts

        # Cache with TTL
        self.cache_duration = timedelta(hours=6)  # Reduced from 24 hours for more frequent updates
        self.discovered_accounts: Dict[str, Dict[str, dict]] = defaultdict(dict)
        self.last_discovery: Dict[str, datetime] = {}

        if all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
            self.twitter_client = self._init_twitter_client(
                twitter_api_key,
                twitter_api_secret,
                twitter_access_token,
                twitter_access_secret
            )

        if youtube_api_key:
            self.youtube_client = self._init_youtube_client(youtube_api_key)

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

    async def find_related_accounts(self, seed_accounts: List[str]) -> Dict[str, List[Dict]]:
        """Find related trading accounts based on seed accounts with detailed metrics"""
        discovered = {
            'twitter': [],
            'youtube': []
        }

        if self.twitter_client:
            twitter_accounts = await self._discover_twitter_accounts(seed_accounts)
            discovered['twitter'] = twitter_accounts

        if self.youtube_client:
            youtube_channels = await self._discover_youtube_channels(seed_accounts)
            discovered['youtube'] = youtube_channels

        return discovered

    async def _discover_twitter_accounts(self, seed_accounts: List[str]) -> List[Dict]:
        """Discover related Twitter accounts with enhanced metrics"""
        discovered = []
        try:
            for account in seed_accounts:
                await self.twitter_rate_limiter.acquire()

                # Get user's followers who are likely traders
                followers = self.twitter_client.get_followers(
                    screen_name=account,
                    count=100  # Increased from 2
                )

                for follower in followers:
                    if await self._is_influential_trader(follower):
                        metrics = await self._calculate_trader_metrics(follower)
                        discovered.append({
                            'username': follower.screen_name,
                            'metrics': metrics,
                            'source': 'follower',
                            'seed_account': account
                        })

                # Get accounts that the user follows
                await self.twitter_rate_limiter.acquire()
                following = self.twitter_client.get_friends(
                    screen_name=account,
                    count=100  # Increased from 2
                )

                for friend in following:
                    if await self._is_influential_trader(friend):
                        metrics = await self._calculate_trader_metrics(friend)
                        discovered.append({
                            'username': friend.screen_name,
                            'metrics': metrics,
                            'source': 'following',
                            'seed_account': account
                        })

        except Exception as e:
            logger.error(f"Error discovering Twitter accounts: {str(e)}")

        return discovered

    async def _discover_youtube_channels(self, seed_accounts: List[str]) -> Set[str]:
        """Discover related YouTube channels"""
        discovered = set()
        try:
            for account in seed_accounts:
                # Search for channels related to trading
                search_response = self.youtube_client.search().list(
                    q=f"{account} crypto trading",
                    type='channel',
                    part='snippet',
                    maxResults=50
                ).execute()

                for item in search_response.get('items', []):
                    channel_name = item['snippet']['channelTitle']
                    if self._is_trading_channel(item['snippet']):
                        discovered.add(channel_name)

                        # Get related channels
                        channel_id = item['snippet']['channelId']
                        related_channels = self._get_related_channels(channel_id)
                        discovered.update(related_channels)

        except HttpError as e:
            logger.error(f"Error discovering YouTube channels: {str(e)}")

        return discovered

    def _get_related_channels(self, channel_id: str) -> Set[str]:
        """Get related channels for a YouTube channel"""
        related = set()
        try:
            # Get channel's featured channels
            channels_response = self.youtube_client.channels().list(
                id=channel_id,
                part='brandingSettings'
            ).execute()

            if channels_response['items']:
                featured_channels = channels_response['items'][0].get(
                    'brandingSettings', {}
                ).get('channel', {}).get('featuredChannelsUrls', [])

                if featured_channels:
                    channels_info = self.youtube_client.channels().list(
                        id=','.join(featured_channels),
                        part='snippet'
                    ).execute()

                    for channel in channels_info.get('items', []):
                        if self._is_trading_channel(channel['snippet']):
                            related.add(channel['snippet']['title'])

        except HttpError as e:
            logger.error(f"Error getting related channels: {str(e)}")

        return related

    async def _is_influential_trader(self, user) -> bool:
        """Enhanced check for influential traders with more sophisticated metrics"""
        if not user.verified and self.min_verified_status:
            return False

        trading_keywords = {
            'trader': 2,
            'trading': 2,
            'crypto': 1,
            'bitcoin': 1,
            'ethereum': 1,
            'analyst': 1.5,
            'investor': 1.5,
            'finance': 1,
            'blockchain': 1,
            'market': 1,
            'technical analysis': 2,
            'fundamental analysis': 2,
            'defi': 1.5
        }

        description = user.description.lower() if user.description else ""
        name = user.name.lower() if user.name else ""

        # Calculate keyword score
        keyword_score = sum(weight for keyword, weight in trading_keywords.items()
                          if keyword in description or keyword in name)

        # Calculate engagement score
        engagement_rate = user.followers_count / max(user.friends_count, 1)
        activity_rate = user.statuses_count / max((datetime.now() - user.created_at).days, 1)

        return (
            user.followers_count >= self.min_follower_count and
            engagement_rate >= self.min_engagement_rate and
            activity_rate >= 0.5 and  # At least one tweet every 2 days
            keyword_score >= 3  # Require multiple relevant keywords
        )

    async def _calculate_trader_metrics(self, user) -> Dict:
        """Calculate detailed metrics for a trader account"""
        return {
            'followers_count': user.followers_count,
            'engagement_rate': user.followers_count / max(user.friends_count, 1),
            'activity_rate': user.statuses_count / max((datetime.now() - user.created_at).days, 1),
            'verified': user.verified,
            'account_age_days': (datetime.now() - user.created_at).days,
            'avg_tweets_per_day': user.statuses_count / max((datetime.now() - user.created_at).days, 1),
            'listed_count': user.listed_count,
            'has_website': bool(user.url)
        }

    def _is_trading_channel(self, snippet: Dict) -> bool:
        """Check if a YouTube channel is trading-related"""
        keywords = [
            'trading', 'crypto', 'bitcoin', 'cryptocurrency',
            'blockchain', 'investment', 'finance', 'market analysis'
        ]

        title = snippet.get('title', '').lower()
        description = snippet.get('description', '').lower()

        return any(keyword in title or keyword in description
                  for keyword in keywords)
