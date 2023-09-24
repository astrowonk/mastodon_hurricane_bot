from lxml import etree
from html2text import html2text
import requests
from bs4 import BeautifulSoup
from mastodon import Mastodon
from config import API_TOKEN, API_BASE_URL
import re
import argparse
import json
import datetime
import sys

CURRENT_URL = 'https://www.nhc.noaa.gov/index-at.xml'


def process_item(item):
    """process one rss item into a dictionary"""
    return {x.tag: x.text for x in item}


def check_rss_updated(CURRENT_URL):
    our_headers = ["Last-Modified", "etag"]
    try:
        with open('status_data.json', 'r') as f:
            status_data = json.load(f)
    except:
        status_data = {}

    r = requests.head(CURRENT_URL)
    new_data = {key: r.headers[key] for key in our_headers}
    print(f"new etag {new_data['etag']}, old etag {status_data['etag']}")
    return any(status_data.get(x) != new_data.get(x)
               for x in our_headers), new_data


def json_write(data, file_name):
    with open(file_name, 'w') as f:
        json.dump(data, f)


def write_new_status_data(status_data):
    json_write(status_data, 'status_data.json')


def process_url(url):
    """use lxml to extract the items and process into dicts"""
    r = requests.get(url)
    mytree = etree.fromstring(r.content)
    theitems = mytree.getchildren()[0].findall('item')
    return [process_item(x) for x in theitems]


def check_summary_guid_change(data_for_post):
    try:
        with open('full_post_data.json', 'r') as f:
            old_post_data = json.load(f)
    except:
        old_post_data = {}

    return old_post_data.get('summary_guid') != data_for_post['summary_guid']


def process_data(data_list):
    """extract the needed data for Mastodon"""
    if len(data_list) < 6:
        return
    out = {}
    out['full_advisory_link'] = data_list[2]['link']
    out['full_advisory_title'] = data_list[2]['title']
    out['summary_title'] = data_list[1]['title']
    out['summary_guid'] = data_list[1]['guid']
    out['summary'] = html2text(data_list[1]['description']).replace('\n', ' ')
    soup = BeautifulSoup(data_list[6]['description'], 'html.parser')
    out['graphic_data'] = requests.get(soup.find('img')['src']).content
    out['graphic_link'] = soup.find('a')['href']
    return out


def make_post_content(data_for_post):
    """with the data dictionary, create the text for the post."""
    clean_title = re.sub(r"\(.+\)", '',
                         data_for_post['summary_title']).strip().replace(
                             "Tropical Storm", 'T.S.')
    pattern = r'\.\.\.(.*?)\.\.\.'

    # Use re.sub() to remove the ellipsis and replace with the captured text and a single period
    cleaner_summary = re.sub(pattern, r'\1.', data_for_post['summary'])

    sentences = cleaner_summary.split(". ")

    non_headline = ". ".join(sentences[2:])

    rem = re.match(
        r"|Tropical Storm|Tropical Depression|Hurricane| (\S+) Public Advisory Number (.+)",
        data_for_post['full_advisory_title'])
    advisory_number = rem.group(2)

    ### F String
    post_content = (
        f"{clean_title}\n\n"
        f"{sentences[0].strip()}.\n\n"
        f"{sentences[1].strip()}.\n\n"
        f"{non_headline}\n\n"
        f"Graphics: {data_for_post['graphic_link']}\n"
        f"Advisory {advisory_number}: {data_for_post['full_advisory_link']}\n\n"
        f"#{rem.group(1)}")

    return post_content, non_headline


def make_and_post(post_content, data_for_post, alt_text):

    m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
    med_dict = m.media_post(data_for_post['graphic_data'],
                            mime_type='image/png',
                            description=alt_text)
    out = m.status_post(post_content, media_ids=med_dict)
    print(
        f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
    )
    write_new_status_data(status_data=status_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--nopost', action='store_true', default=False)
    parser.add_argument('--force-update', action='store_true', default=False)

    args = parser.parse_args()
    is_updated, status_data = check_rss_updated(CURRENT_URL)
    if is_updated or args.force_update:
        if args.force_update:
            print("update forced, ignoring status header data.")

        data_for_post = process_data(process_url(CURRENT_URL))
        if not data_for_post:
            sys.exit()
        post_content, non_headline = make_post_content(data_for_post)

        if check_summary_guid_change(data_for_post) or args.force_update:

            make_and_post(post_content,
                          data_for_post=data_for_post,
                          alt_text=non_headline + '\n' +
                          "See post for description and links to storm path.")
            del data_for_post['graphic_data']
            json_write(data_for_post, 'full_post_data.json')

        else:
            print(
                f"Guid for summary unchanged at {datetime.datetime.now().isoformat()}"
            )
            print("No posting to Mastodon")
            write_new_status_data(status_data)
            print(post_content)
    else:
        print("No updated feed data.")
