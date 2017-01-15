import logging
import re
import smtplib

from collections import defaultdict
from datetime import timedelta
from email.mime.text import MIMEText
from urllib.parse import urlparse
from sys import exit
from time import sleep
from xml.etree import ElementTree as ET

from click import command, option, argument, echo
from click.types import IntRange
import dateparser
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


def send_results(results, address):
    msg = []

    for pattern, found in results.items():
        msg.append('<h3>For "%s" pattern:<\h3>' % pattern)
        for title, published, link in found:
            msg.append('\t* [%s] <a href=%s>%s</a>' % (published, link, title))

    msg = MIMEText('\n'.join(msg))
    msg['Subject'] = 'Notification from rss_checker'
    msg['From'] = 'rss_checker@mac'
    msg['To'] = address

    try:
        s = smtplib.SMTP('localhost')
    except ConnectionRefusedError:
        fail('Cannot connect to local smtp server, is it running?')
    s.send_message(msg)
    s.quit()


def check_feed(site, patterns):
    res = get(site)
    return find(res, patterns)


@command()
@argument('site')
@option('-p', '--pattern', 'patterns', multiple=True, required=True,
        help='Pattern which should be searched, case is ignored')
@option('--email', help='Address to which results should be sent')
@option('--from-date', help='From what time you want events',
        default='1 day ago')
@option('-i', '--interval', type=IntRange(min=0))
def check(site, patterns, email, interval, from_date):
    if type(from_date) is str:
        from_date = dateparser.parse(from_date)

    logger.info('Checking feed starting from %s', from_date)
    found = check_feed(site, patterns)

    if email:
        send_results(found, email)

    print_results(found)

    if interval:
        sleep(interval)
        check.callback(site, patterns, email, interval,
                       from_date + timedelta(seconds=interval))


if __name__ == '__main__':
    check()
