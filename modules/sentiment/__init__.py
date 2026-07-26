"""NEXUS AI — Sentiment Intelligence Module Exports"""
from .news_sentiment    import NewsSentimentAnalyzer, SentimentResult, NewsItem, news_sentiment
from .social_sentiment  import (
    SocialSentimentTracker, SocialSentimentResult,
    FearGreedData, BreadthData, social_sentiment,
)
from .sentiment_engine  import SentimentEngine, SentimentSignal, sentiment_engine

__all__ = [
    "NewsSentimentAnalyzer", "SentimentResult", "NewsItem", "news_sentiment",
    "SocialSentimentTracker", "SocialSentimentResult", "FearGreedData", "BreadthData", "social_sentiment",
    "SentimentEngine", "SentimentSignal", "sentiment_engine",
]
