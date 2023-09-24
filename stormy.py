import re
from bs4 import BeautifulSoup
import requests
from html2text import html2text
from config import API_BASE_URL, API_TOKEN
from mastodon import Mastodon
import json


class Stormy:

    def __init__(self, data_list):
        assert len(data_list) == 6, "data set must be length 6"
        self.data_list = data_list
        self.process_data()
        self.set_storm_id()
        self.make_post_content()

    def set_storm_id(self):
        self.storm_id = re.search(r"\((.+)\)",
                                  self.data_for_post['summary_title']).group(1)
        self.data_for_post['storm_id'] = self.storm_id.replace('/', '_')

    def process_data(self):
        """extract the needed data for Mastodon"""
        out = {}
        out['full_advisory_link'] = self.data_list[1]['link']
        out['full_advisory_title'] = self.data_list[1]['title']
        out['summary_title'] = self.data_list[0]['title']
        out['summary_guid'] = self.data_list[0]['guid']
        out['summary'] = html2text(self.data_list[0]['description']).replace(
            '\n', ' ')
        soup = BeautifulSoup(self.data_list[5]['description'], 'html.parser')
        out['graphic_data'] = requests.get(soup.find('img')['src']).content
        out['graphic_link'] = soup.find('a')['href']
        self.data_for_post = out

    def make_post_content(self):
        """with the data dictionary, create the text for the post."""
        clean_title = re.sub(r"\(.+\)", '',
                             self.data_for_post['summary_title']).strip()
        self.storm_code = re.search(
            r"\((.+)\)", self.data_for_post['summary_title']).group(1)
        pattern = r"(Tropical Depression |Hurricane |Tropical Storm|Post-Tropical Cyclone )"
        clean_title = re.sub(pattern, '', clean_title)

        # Use re.sub() to remove the ellipsis and replace with the captured text and a single period
        pattern = r'\.\.\.(.*?)\.\.\.'
        cleaner_summary = re.sub(pattern, r'\1.',
                                 self.data_for_post['summary'])

        sentences = cleaner_summary.split(". ")

        non_headline = ". ".join(sentences[2:])

        pattern = r"(?:Tropical Depression|Hurricane|Tropical Storm|Post-Tropical Cyclone) (.+) Public Advisory Number (.+)"
        rem = re.match(pattern, self.data_for_post['full_advisory_title'])
        advisory_number = rem.group(2)

        ### F String
        post_content = (
            f"{clean_title}\n\n"
            f"{sentences[0].strip()}.\n\n"
            f"{sentences[1].strip()}.\n\n"
            f"{non_headline}\n\n"
            f"Track: {self.data_for_post['graphic_link']}\n"
            f"Advisory {advisory_number}: {self.data_for_post['full_advisory_link']}\n\n"
            f"#{rem.group(1)}")

        self.post_content, self.non_headline = post_content, non_headline

    def post_to_mastodon(self):
        """Use data to post to Mastodon instance"""
        m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
        med_dict = m.media_post(self.data_for_post['graphic_data'],
                                mime_type='image/png',
                                description=self.non_headline)
        out = m.status_post(self.post_content, media_ids=med_dict)
        print(
            f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
        )