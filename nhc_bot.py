from lxml import etree
import requests
from mastodon import Mastodon
from config import API_TOKEN
import argparse
import json
import datetime
from stormy import Stormy, Summary
import traceback
from utils import print_to_slack

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


def json_write(data, file_name):
    with open(file_name, 'w') as f:
        json.dump(data, f)


def write_new_status_data(status_data):
    json_write(status_data, 'status_data.json')


def process_url(url=None, text=None):
    """use lxml to extract the items and process into dicts"""
    assert url or text, 'must have string or url'
    if url:
        r = requests.get(url)
        text = r.content
    mytree = etree.fromstring(text)
    theitems = mytree.getchildren()[0].findall('item')
    return [process_item(x) for x in theitems]


def get_summary_data(out):
    try:
        with open('summary.json', 'r') as f:
            old_summary_data = json.load(f)
    except:
        old_summary_data = {}
    return old_summary_data


def check_summary_guid_change(out):
    """checking if the guid has changed on the tropics summary"""
    guid = out['guid']
    old_summary_data = get_summary_data(out)

    return old_summary_data.get('guid') != guid


def check_storm_guid_change(data_for_post):
    storm_id = data_for_post['storm_id']
    try:
        with open(f'{storm_id}_full_post_data.json', 'r') as f:
            old_post_data = json.load(f)
    except:
        old_post_data = {}

    return (old_post_data.get('summary_guid') != data_for_post['summary_guid']) and (
        old_post_data.get('summary').strip() != data_for_post['summary'].strip()
    )


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
            if len(storm_list) > 1 and check_summary_guid_change(out[0]):
                theSummary = Summary(out[0])
                theSummary.post_to_mastodon()
                json_write(out[0], 'summary.json')
            else:
                if not check_summary_guid_change(out[0]):
                    print_to_slack('Guid for summary unchanged, no post of summary image.')
                else:
                    print_to_slack('Only 1 storm, no summary')
            for raw_data in storm_list:
                graphic_hash = get_summary_data(raw_data).get('graphic_hash')

                s = Stormy(raw_data)

                data_for_post = s.data_for_post.copy()
                if check_storm_guid_change(s.data_for_post) or args.force_update:
                    if not args.no_post:
                        print_to_slack('Posting to Mastodon.')
                        print_to_slack(f"Guid for storm {data_for_post['summary_guid']}")
                        old_summary_data = get_summary_data(out)

                        p_bool, p_status = s.post_to_mastodon(verify_image_hash=graphic_hash)
                        print_to_slack(p_status)
                        if p_bool:
                            del data_for_post['graphic_data']
                            storm_id = data_for_post['storm_id']
                            json_write(data_for_post, f'{storm_id}_full_post_data.json')
                    else:
                        print_to_slack(
                            f'Posting disabled. Sending post content to log. Length: {len(s.post_content)}'
                        )
                        print_to_slack(s.post_content)

                else:
                    print_to_slack(
                        f"Guid for storm {data_for_post['storm_id']} unchanged at {datetime.datetime.now().isoformat()}"
                    )
                    print_to_slack('No posting to Mastodon')
            write_new_status_data(status_data)
        else:
            print_to_slack('No updated feed data.')
    except Exception as e:
        tb = ''.join(traceback.format_exception(e))
        print_to_slack(f'Error in Huricane bot: \n{tb}', error=True)
