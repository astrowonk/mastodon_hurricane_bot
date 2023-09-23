from lxml import etree
from html2text import html2text
import requests
from bs4 import BeautifulSoup
from mastodon import Mastodon
from config import API_TOKEN, API_BASE_URL
import re
import argparse

CURRENT_URL = 'https://www.nhc.noaa.gov/index-at.xml'


def process_item(item):
    return {x.tag: x.text for x in item}


def process_url(url):
    r = requests.get(url)
    mytree = etree.fromstring(r.content)
    theitems = mytree.getchildren()[0].findall('item')
    return [process_item(x) for x in theitems]


def process_data(data_list):
    out = {}
    out['full_advisory_link'] = data_list[2]['link']
    out['full_advisory_title'] = data_list[2]['title']
    out['summary_title'] = data_list[1]['title']
    out['summary'] = html2text(data_list[1]['description']).replace('\n', ' ')
    soup = BeautifulSoup(data_list[6]['description'], 'html.parser')
    out['graphic_data'] = requests.get(soup.find('img')['src']).content
    out['graphic_link'] = soup.find('a')['href']
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--nopost', action='store_true', default=False)

    args = parser.parse_args()

    test_data = process_data(process_url(CURRENT_URL))
    clean_title = re.sub(r"\(.+\)", '',
                         test_data['summary_title']).strip().replace(
                             "Tropical Storm", 'T.S.')
    pattern = r'\.\.\.(.*?)\.\.\.'

    # Use re.sub() to remove the ellipsis and replace with the captured text and a single period
    cleaner_summary = re.sub(pattern, r'\1.', test_data['summary'])

    sentences = cleaner_summary.split(". ")

    non_headline = ". ".join(sentences[2:])

    rem = re.match(r"Tropical Storm (\S+) Public Advisory Number (.+)",
                   test_data['full_advisory_title'])
    advisory_number = rem.group(2)

    post_content = f"""
{clean_title}

{sentences[0].strip()}
{sentences[1].strip()}

{non_headline}

{test_data['graphic_link']}

Advisory {advisory_number}: {test_data['full_advisory_link']}

#{rem.group(1)}"""

    if not args.nopost:
        m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
        med_dict = m.media_post(test_data['graphic_data'],
                                mime_type='image/png')
        out = m.status_post(post_content, media_ids=med_dict)
        print(
            f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
        )
    else:
        print(post_content)
