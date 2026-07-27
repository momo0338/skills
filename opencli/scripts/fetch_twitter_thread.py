#!/usr/bin/env python3
"""
fetch_twitter_thread.py - Reliable Twitter/X Thread Fetcher

Solves Twitter/X anti-scraping & login-wall limits when reading long tweet threads:
1. Uses Twitter Syndication API (cdn.syndication.twimg.com/tweet-result) for public status retrieval.
2. Uses opencli search with `from:<user>` filter to bypass login-wall thread pagination limits.
3. Automatically orders and formats the complete thread into clean Markdown.
"""

import sys
import re
import json
import urllib.request
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor

def get_tweet_by_id(tweet_id):
    """Fetch single tweet metadata from Twitter Syndication API."""
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=x"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    try:
        res = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        return json.loads(res)
    except Exception as e:
        return None

def fetch_thread_by_opencli_search(author, keywords):
    """Fallback search via opencli to grab tweets from author."""
    results = {}
    for kw in keywords:
        q = f"from:{author} {kw}"
        try:
            cmd = ['opencli', 'twitter', 'search', q, '-f', 'json']
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8')
            data = json.loads(out)
            for t in data:
                tid = str(t.get('id'))
                results[tid] = t.get('text', '')
        except Exception:
            pass
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_twitter_thread.py <tweet_url_or_id>")
        sys.exit(1)

    target = sys.argv[1].strip()
    match = re.search(r'status/(\d+)', target)
    tweet_id = match.group(1) if match else target

    if not tweet_id.isdigit():
        print(f"Error: Invalid tweet ID or URL: {target}")
        sys.exit(1)

    print(f"[*] Fetching root tweet {tweet_id} via Syndication API...")
    root_data = get_tweet_by_id(tweet_id)
    if not root_data:
        print(f"[-] Failed to fetch root tweet {tweet_id}")
        sys.exit(1)

    author = root_data.get('user', {}).get('screen_name')
    author_name = root_data.get('user', {}).get('name')
    root_text = root_data.get('text', '')

    print(f"[+] Root Tweet Author: @{author} ({author_name})")
    print(f"[+] Root Text: {root_text[:60]}...")

    # Extract keywords from root text to search for thread items
    words = re.findall(r'[\u4e00-\u9fa5A-Za-z0-9]+', root_text)
    search_keywords = [w for w in words if len(w) >= 2][:5]
    search_keywords.extend(['Prompt', 'prompt', '【', '1/', '2/', '3/'])

    print(f"[*] Searching for thread replies from @{author} using opencli...")
    thread_tweets = fetch_thread_by_opencli_search(author, search_keywords)

    # Ensure root tweet is included
    thread_tweets[str(tweet_id)] = root_text

    print(f"\n==================== FULL THREAD (@{author}) ====================")
    for tid, txt in sorted(thread_tweets.items(), key=lambda x: int(x[0])):
        print(f"\n--- Status ID: {tid} ---")
        print(txt)

if __name__ == '__main__':
    main()
