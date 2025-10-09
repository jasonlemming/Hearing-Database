"""
Ingester modules for fetching and processing research content
"""
from .base import BaseIngester
from .brookings import BrookingsIngester

__all__ = ['BaseIngester', 'BrookingsIngester']
