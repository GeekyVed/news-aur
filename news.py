#!/usr/bin/env python3

import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import html
import re
import os
import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime

RSS_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.techradar.com/feeds/news",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.theverge.com/theverge/index.xml",
    "https://dev.to/feed",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning", "neural",
    "algorithm", "computer science", "programming", "software", "developer",
    "coding", "python", "rust", "golang", "linux", "kernel", "cybersecurity",
    "hacker", "data science", "llm", "gpt", "transformer", "compiler",
    "distributed system", "cloud computing", "aws", "azure", "google cloud"
]

MAX_ITEMS = 4
CACHE_FILE = os.path.expanduser("~/.cache/news_fetcher.xml")
CACHE_DURATION = 3600  # 1 hour

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    # Colors
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'

def clean_html(raw_html):
    """Remove HTML tags and decode entities."""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return html.unescape(cleantext).strip()

def fetch_feed(url):
    """Fetch a single RSS feed with timeout."""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read()
    except Exception:
        return None

def parse_date(date_str):
    """Parse RSS date string to datetime object."""
    if not date_str:
        return datetime.min
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return datetime.min

import argparse
import random
import threading
import itertools
from urllib.parse import urlparse

class Spinner:
    def __init__(self, message="Fetching news...", delay=0.1):
        self.spinner = itertools.cycle(['|', '/', '-', '\\'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message
        # Calculate visible length by stripping ANSI codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.message_len = len(ansi_escape.sub('', message))

    def write_next(self):
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(self.message + " ")
                self.spinner_visible = True
            sys.stdout.write(next(self.spinner))
            sys.stdout.flush()
            sys.stdout.write('\b')
            sys.stdout.flush()

    def run(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
        self.remove_spinner()

    def remove_spinner(self):
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write('\b')
                sys.stdout.flush()
                # Overwrite with spaces (reset color first to avoid background issues)
                sys.stdout.write(Colors.ENDC + " " * (self.message_len + 2)) 
                sys.stdout.write('\r')
                sys.stdout.flush()
                self.spinner_visible = False

    def __enter__(self):
        if sys.stdout.isatty():
            self._screen_lock = threading.Lock()
            self.busy = True
            # Hide cursor
            sys.stdout.write('\033[?25l')
            sys.stdout.flush()
            self.thread = threading.Thread(target=self.run)
            self.thread.start()
        return self

    def __exit__(self, exception, value, tb):
        if sys.stdout.isatty():
            self.busy = False
            self.remove_spinner()
            # Show cursor
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
            self.thread.join()

def get_news(shuffle=False, limit=MAX_ITEMS):
    """Fetch, parse, filter, and sort news items."""
    all_items = []
    
    # We want deterministic output for the "same set of news".
    # Sorting by date ensures that.
    
    for url in RSS_FEEDS:
        data = fetch_feed(url)
        if not data:
            continue
            
        try:
            root = ET.fromstring(data)
            # Handle standard RSS 2.0 and Atom (basic support)
            # Most listed feeds are RSS 2.0
            channel = root.find('channel')
            if channel is None: 
                # Try Atom namespace if needed, but keeping it simple for now as feeds are known
                continue
                
            for item in channel.findall('item'):
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                if not title:
                    continue

                # Filter
                title_lower = title.lower()
                desc_lower = desc.lower() if desc else ""
                
                # Create a combined text for searching
                combined_text = f"{title_lower} {desc_lower}"
                
                # Check for keywords with word boundaries
                # Pre-compile regexes for performance if list is long, but here it's fine
                is_match = False
                for k in KEYWORDS:
                    # Escape keyword just in case, though ours are safe
                    pattern = r'\b' + re.escape(k) + r'\b'
                    if re.search(pattern, combined_text):
                        is_match = True
                        break
                
                if is_match:
                    all_items.append({
                        'title': title.strip(),
                        'link': link.strip(),
                        'desc': clean_html(desc)[:200] + "..." if desc else "No description.",
                        'date': parse_date(pubDate),
                        'source': url
                    })
        except ET.ParseError:
            continue

    if shuffle:
        random.shuffle(all_items)
    else:
        # Sort by date descending (newest first)
        # This makes it deterministic: same feeds -> same order
        all_items.sort(key=lambda x: x['date'], reverse=True)
    
    return all_items[:limit]

def print_clickable_link(text, url):
    """Print a terminal clickable link."""
    # OSC 8 ; params ; url ST text OSC 8 ;; ST
    sys.stdout.write(f"\033]8;;{url}\033\\{text}\033]8;;\033\\\n")

def main():
    parser = argparse.ArgumentParser(description="Fetch CS & AI News")
    parser.add_argument("-r", "--random", action="store_true", help="Shuffle news items instead of sorting by date")
    parser.add_argument("-l", "--limit", type=int, default=MAX_ITEMS, help="Number of news items to display")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.BLUE}  === Latest CS & AI News ==={Colors.ENDC}\n")
    
    with Spinner(f"{Colors.CYAN}Fetching news feeds...{Colors.ENDC}"):
        items = get_news(shuffle=args.random, limit=args.limit)
    
    if not items:
        print(f"{Colors.WARNING}No relevant news found at this time.{Colors.ENDC}")
        return

    for item in items:
        domain = urlparse(item['source']).netloc.replace('www.', '')
        date_str = item['date'].strftime('%Y-%m-%d %H:%M') if item['date'] != datetime.min else "Recent"

        print(f"{Colors.BOLD}{Colors.CYAN}• {item['title']}{Colors.ENDC}")
        print(f"  {Colors.DIM}{domain} | {date_str}{Colors.ENDC}")
        print(f"  {Colors.WHITE}{item['desc']}{Colors.ENDC}")
        sys.stdout.write(f"  {Colors.BLUE}Read more: {Colors.ENDC}")
        print_clickable_link(item['link'], item['link'])
        print(f"{Colors.DIM}{'-'*60}{Colors.ENDC}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
