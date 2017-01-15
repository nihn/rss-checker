import logging
import re

from collections import defaultdict
from urllib.parse import urlparse
from sys import exit
from xml.etree import ElementTree as ET

from click import command, option, argument, echo
import requests

logging.basicConfig(level=logging.INFO)
logging.getLogger('requests').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def fail(msg, *args):
    logger.error(msg, *args)
    exit(1)


def parse_item(item):
    title = item.find('title').text
    link = item.find('link').text
    published = item.find('pubDate').text
    categories = [cat.text for cat in item.findall('category') or []]

    return {link: {'categories': categories, 'title': title,
                   'published': published}}


def get(address):
    parsed = urlparse(address)

    if not parsed.hostname and '/' not in parsed.path:
        address += '/feed'

    if not parsed.scheme:
        address = 'http://' + address

    logger.info('Getting feed from %s...', address)
    res = requests.get(address, timeout=5)

    if res.status_code != 200:
        fail('Got %d response code from server', res.status_code)

    return parse_feed_xm(res.content)


def parse_feed_xm(xml_string):
    try:
        channel = ET.fromstring(xml_string).find('channel')
    except ET.ParseError:
        fail('Response from server does not contains valid rss xml')

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
                matches[pattern.pattern].append(
                    (details['title'], details['published'], link))

    return matches


def print_results(results):
    for pattern, found in results.items():
        echo('%s:' % pattern)
        for title, published, link in found:
            echo('\t* [%s] %s: %s' % (published, title, link))
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
