from collections import defaultdict
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import re

import requests


def parse_item(item):
    title = item.find('title').text
    link = item.find('link').text
    categories = [cat.text for cat in item.findall('category') or []]

    return {link: {'categories': categories, 'title': title}}


def get(address):
    parsed = urlparse(address)
    scheme = parsed.scheme or 'http'
    path = parsed.path or 'feed'
    res = requests.get('%s://%s/%s' % (scheme, parsed.hostname, path), timeout=5)

    channel = ET.fromstring(res.content).find('channel')
    results = {}

    for item in channel.findall('item'):
        results.update(parse_item(item))

    return results


def find(results, patterns):
    matches = defaultdict(list)
    patterns = [re.compile(pattern) for pattern in patterns]

    for link, details in results.items():
        for pattern in patterns:
            if any(pattern.search(cat, re.IGNORECASE)
                   for cat in details['categories'] + [details['title']]):
                matches[pattern.pattern].append((details['title'], link))

    return matches


res = get('http://fly4free.pl')
found = find(res, [r'wroclaw\w*', 'katowic\w*', 'warszaw\w+'])

for p, f in found.items():
    print('%s:' % p)
    for title, link in f:
        print('\t* %s: %s' % (title, link))
