from lxml import etree
import requests
from mastodon import Mastodon
from config import API_TOKEN
import argparse
import json
import datetime
from stormy import Stormy, Summary
import traceback
from utils import print_to_slack, write_new_status_data

VERIFY = False

CURRENT_URL = 'https://www.nhc.noaa.gov/index-at.xml'


def process_item(item):
    """process one rss item into a dictionary"""
    return {x.tag: x.text for x in item}


def check_rss_updated(CURRENT_URL):
    our_headers = ['Last-Modified', 'etag']
    try:
        with open('status_data.json', 'r') as f:
            status_data = json.load(f)
    except:
        status_data = {}

    r = requests.head(CURRENT_URL)
    new_data = {key: r.headers[key] for key in our_headers}
    print_to_slack(
        f"{datetime.datetime.now().isoformat()} new etag {new_data['etag']}, old etag {status_data['etag']}"
    )
    return any(status_data.get(x) != new_data.get(x) for x in our_headers), new_data


def process_url(url=None, text=None):
    """use lxml to extract the items and process into dicts"""
    assert url or text, 'must have string or url'
    if url:
        r = requests.get(url)
        text = r.content
    mytree = etree.fromstring(text)
    theitems = mytree.getchildren()[0].findall('item')
    return [process_item(x) for x in theitems]


def make_list_of_storms(out):
    """Since there can be multiple storms, find the summary and then the next 5 entries for each."""
    new_out = []
    new_storm = []
    for item in out:
        if item['title'].endswith('Weather Outlook'):
            continue
        print(len(new_storm))
        if item['title'].startswith('Summary'):
            if new_storm:
                new_out.append(new_storm)
                new_storm = []
            new_storm.append(item)
        else:
            new_storm.append(item)
    # append final storm
    new_out.append(new_storm)

    return new_out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-post', action='store_true', default=False)
    parser.add_argument('--force-update', action='store_true', default=False)

    args = parser.parse_args()

    try:
        is_updated, status_data = check_rss_updated(CURRENT_URL)
        if is_updated or args.force_update:
            if args.force_update:
                print_to_slack('update forced, ignoring status header data.')

            out = process_url(CURRENT_URL)
            storm_list = make_list_of_storms(out)
            print_to_slack(f'Storm list is length {len(storm_list)}')
            for storm_data in storm_list:
                s = Stormy(storm_data)

                s.run(args.force_update, args.no_post)
        else:
            print_to_slack('No updated feed data.')
        write_new_status_data(status_data)
    except Exception as e:
        tb = ''.join(traceback.format_exception(e))
        print_to_slack(f'Error in Huricane bot: \n{tb}', error=True)
        print_to_slack(s.post_content, error=True)
