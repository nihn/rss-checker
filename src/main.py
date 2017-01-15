import logging
import re

from collections import defaultdict
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from click import command, option, argument, echo
import requests

logging.basicConfig(level=logging.INFO)


def parse_item(item):
    title = item.find('title').text
    link = item.find('link').text
    categories = [cat.text for cat in item.findall('category') or []]

    return {link: {'categories': categories, 'title': title}}


def get(address):
    parsed = urlparse(address)

    if not parsed.scheme:
        address = 'http://' + address

    if not parsed.path:
        address += '/feed'

    res = requests.get(address, timeout=5)

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


def print_results(results):
    for pattern, found in results.items():
        echo('%s:' % pattern)
        for title, link in found:
            echo('\t* %s: %s' % (title, link))
        echo('\n')


@command()
@argument('site')
@option('-p', '--pattern', 'patterns', multiple=True, required=True,
        help='Pattern which should be searched, case is ignored')
def check(site, patterns):
    res = get(site)
    found = find(res, patterns)
    print_results(found)


if __name__ == '__main__':
    check()
