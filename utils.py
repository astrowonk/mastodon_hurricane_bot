from config import SLACK_URL, SLACK_ERROR_URL
import requests
import json
import os


def print_to_slack(txt, error=False):
    if os.environ.get('NO_SLACK_PRINT'):
        print(txt)
    data = {'text': txt}
    if not error:
        requests.post(url=SLACK_URL, json=data)
    else:
        requests.post(url=SLACK_ERROR_URL, json=data)


def json_write(data, file_name):
    with open(file_name, 'w') as f:
        json.dump(data, f)


def write_new_status_data(status_data):
    json_write(status_data, 'status_data.json')


def get_storm_data(data_for_post):
    storm_id = data_for_post['storm_id']

    try:
        with open(f'{storm_id}_full_post_data.json', 'r') as f:
            old_post_data = json.load(f)
    except:
        old_post_data = {}
    return old_post_data


def check_storm_guid_change(data_for_post):
    old_post_data = get_storm_data(data_for_post)
    # guid is unreliable

    summary_bool = old_post_data.get('summary') != data_for_post.get('summary')
    guid_bool = old_post_data.get('summary_guid') != data_for_post.get('summary_guid')
    print_to_slack(f'New summary bool test is {summary_bool}. (Guid test is {guid_bool})')
    return summary_bool
