from config import SLACK_URL, SLACK_ERROR_URL
import requests


def print_to_slack(txt, error=False):
    data = {'text': txt}
    if not error:
        requests.post(url=SLACK_URL, json=data)
    else:
        requests.post(url=SLACK_ERROR_URL, json=data)
