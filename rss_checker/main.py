import logging
import re
import smtplib

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.mime.text import MIMEText
from functools import partial
from urllib.parse import urlparse
from sys import exit
from time import sleep
from xml.etree import ElementTree as ET

from click import command, option, argument, echo
from click.types import IntRange, File
import dateparser
import requests
import yaml

logging.basicConfig(level=logging.INFO)
logging.getLogger('requests').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
SMTP = None


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
    try:
        res = requests.get(address, timeout=5)
    except requests.RequestException as e:
        logger.error('%s when getting feed from server', e.__class__.__name__)
        return

    if res.status_code != 200:
        logger.error('Got %d response code from server', res.status_code)
        return

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


def find(results, patterns, from_date):
    matches = defaultdict(list)
    patterns = [re.compile(pattern) for pattern in patterns]

    for link, details in results.items():
        if dateparser.parse(details['published']) < from_date:
            continue

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
    msg = ['<html><body>']

    for pattern, found in results.items():
        msg.append('<h3>For "%s" pattern:</h3>\n' % pattern)
        for title, published, link in found:
            msg.append('<p>\t* [%s] <a href=%s>%s</a></p>' % (published, link, title))

    msg.append('</body></html>')

    msg = MIMEText('\n'.join(msg), 'html')
    msg['Subject'] = 'Notification from rss_checker'
    msg['From'] = 'rss_checker@localhost'
    msg['To'] = address

    logger.info('Sending e-mail to %s', address)

    s = setup_smtp()
    try:
        s.send_message(msg)
    except smtplib.SMTPSenderRefused as e:
        logger.error('Failed to send email, error got from server: %s',
                     e.smtp_error)
    s.quit()


def check_feed(site, patterns, from_date):
    res = get(site)
    if res is not None:
        return find(res, patterns, from_date)


def setup_smtp(smtp_config=None):
    global SMTP
    smtp_config = smtp_config or {}

    if SMTP is not None:
        return SMTP

    try:
        SMTP = smtplib.SMTP(smtp_config.get('host', 'localhost'),
                            smtp_config.get('port', 23))
    except ConnectionRefusedError:
        fail('Cannot connect to local smtp server, is it running?')

    SMTP.starttls()

    if 'user' in smtp_config:
        SMTP.login(smtp_config['user'], smtp_config['password'])

    return SMTP


@command()
@argument('site')
@option('-p', '--pattern', 'patterns', multiple=True, required=True,
        help='Pattern which should be searched, case is ignored')
@option('--email', help='Address to which results should be sent')
@option('--from-date', help='From what time you want events',
        default='1 day ago')
@option('-i', '--interval', type=IntRange(min=0),
        help='When set script will relaunch every x seconds and will fetch '
             'results from previous run to present.')
@option('--quite', is_flag=True, help='Do not print results to console')
def check(site, patterns, email, interval, from_date, quite):
    start = datetime.now()

    if type(from_date) is str:
        from_date = dateparser.parse(from_date)

    logger.info('Checking feed starting from %s', from_date)
    found = check_feed(site, patterns, from_date)

    if found:
        if email:
            send_results(found, email)
        if not quite:
            print_results(found)
    elif found is not None:
        logger.info('Nothing found')

    if interval:
        if found is None:
            logger.info('Retrying due to error in processing')
            start = from_date

        sleep(interval)
        check.callback(site, patterns, email, interval, start, quite)


@command()
@option('-c', '--config', type=File())
def checkd(config):
    config = yaml.load(config)

    hosts = config.get('hosts')
    interval = config.get('interval', 60)

    setup_smtp(config.get('smtp'))

    if hosts is None:
        fail('At least on host need to be specified')

    email = config.get('receiver')

    if email is None:
        fail('At least one receiver need to be specified')

    function = partial(check.callback, email=email, interval=interval,
                       from_date='%s seconds ago' % interval, quite=False)

    with ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        res = executor.map(function, hosts.keys(), hosts.values())

    ' '.join(res)

if __name__ == '__main__':
    check()
