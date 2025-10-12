"""
Ingester modules for fetching and processing research content
"""
from .base import BaseIngester
from .brookings import BrookingsIngester
from .substack import SubstackIngester

__all__ = ['BaseIngester', 'BrookingsIngester', 'SubstackIngester']
