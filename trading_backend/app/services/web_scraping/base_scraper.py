import logging
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Base class for all scrapers."""

    def __init__(self, min_confidence: float = 0.1, config: Dict = None, sentiment_analyzer: Optional[Any] = None):
        """Initialize base scraper with configuration."""
        self.config = config or {}
        self.min_confidence = min_confidence
        self.sentiment_analyzer = sentiment_analyzer
        self.base_weights = {
            'bert': 0.4,
            'technical': 0.3,
            'context': 0.3
        }

    @abstractmethod
    async def scrape_platform(self, platform: str, keywords: List[str]) -> List[Dict]:
        """Scrape content from specified platform."""
        pass

    @abstractmethod
    async def analyze_sentiment(self, text: str) -> Tuple[str, float]:
        """Analyze sentiment of text."""
        pass

    def _validate_config(self, required_keys: List[str]) -> bool:
        """Validate configuration has required keys."""
        try:
            for key in required_keys:
                if key not in self.config:
                    logger.error(f"Missing required config key: {key}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error validating config: {str(e)}")
            return False

    def _get_config_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value with optional default."""
        try:
            return self.config.get(key, default)
        except Exception as e:
            logger.error(f"Error getting config value for {key}: {str(e)}")
            return default

    def _log_scraping_error(self, platform: str, error: Exception) -> None:
        """Log scraping errors with consistent format."""
        logger.error(f"Error scraping {platform}: {str(error)}")
        logger.debug(f"Error details for {platform}:", exc_info=True)
