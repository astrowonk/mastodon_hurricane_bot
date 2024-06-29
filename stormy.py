import re
from bs4 import BeautifulSoup
import requests
from html2text import html2text
from config import API_TOKEN
from mastodon import Mastodon

VERIFY = True


class Summary:
    req = None
    active_systems_text = None
    img_data = None

    def __init__(self, summary_dict) -> None:
        self.summary_dict = summary_dict
        self.get_full_storm_webpage()
        self.get_image()

    def get_full_storm_webpage(self):
        self.req = requests.get(self.summary_dict['guid'], verify=VERIFY)

    def get_image(self):
        soup = BeautifulSoup(self.req.text, 'html.parser')
        url_part = soup.select_one('img[id=twofig7d]').get('src')
        url = f'https://www.nhc.noaa.gov/{url_part}'
        self.img_data = requests.get(url, verify=VERIFY).content

    @property
    def post_content(self):
        pattern = r'(Active Systems:[\s\\n]+.+)\$\$'
        search_string = html2text(self.summary_dict['description'])
        m = re.search(pattern, ' '.join(search_string.split()))
        regex_text = m.group(1).strip().replace('Active Systems: ', '')
        return regex_text + '\n\n' + self.summary_dict['link']

    def post_to_mastodon(self):
        m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
        med_dict = m.media_post(
            self.img_data, mime_type='image/png', description=self.post_content
        )
        out = m.status_post(self.post_content, media_ids=med_dict)
        print(
            f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
        )


class Stormy:
    def __init__(self, data_list):
        """Inited with a list of 6 dictionaries created by process_item and make_list_of_storms"""
        assert len(data_list) == 6, 'data set must be length 6'
        self.data_list = data_list
        self.process_data()
        self.set_storm_id()
        self.make_post_content()

    def set_storm_id(self):
        """get the storm id from the summary with regex"""
        self.storm_id = re.search(r'\((.+)\)', self.data_for_post['summary_title']).group(1)
        self.data_for_post['storm_id'] = self.storm_id.replace('/', '_')

    def process_data(self):
        """extract the needed data for Mastodon from the full tag:text list of dictionaries"""
        self.data_for_post = {}
        self.data_for_post['full_advisory_link'] = self.data_list[1]['link']
        self.data_for_post['full_advisory_title'] = self.data_list[1]['title']
        self.data_for_post['summary_title'] = self.data_list[0]['title']
        self.data_for_post['summary_guid'] = self.data_list[0]['guid']
        self.data_for_post['summary'] = (
            html2text(self.data_list[0]['description']).replace('\n', ' ').strip()
        )
        soup = BeautifulSoup(self.data_list[5]['description'], 'html.parser')
        graphic_url = soup.find('img')['src']
        pattern = r'_sm2\.png$'
        # change url so we can not use the small image, but a higher resolution one.
        graphic_url = re.sub(pattern=pattern, repl='.png', string=graphic_url)
        self.data_for_post['graphic_data'] = requests.get(
            graphic_url, verify=VERIFY, headers={'Cache-Control': 'no-cache'}
        ).content
        self.data_for_post['graphic_link'] = soup.find('a')['href']

        self.storm_code = re.search(r'\((.+)\)', self.data_for_post['summary_title']).group(1)

        pattern = r'(.+) (\S+) Public Advisory Number (.+)$'
        rem = re.match(pattern, self.data_for_post['full_advisory_title'])
        self.data_for_post['advisory_number'] = rem.group(3)
        self.data_for_post['storm_type'] = rem.group(1)
        self.data_for_post['storm_name'] = rem.group(2).strip()

    def make_post_content(self):
        """with the data dictionary, create the text for the post."""
        # Use re.sub() to remove the ellipsis and replace with the captured text and a single period
        pattern = r'\.\.\.(.*?)\.\.\.'
        cleaner_summary = re.sub(pattern, r'\1.', self.data_for_post['summary'])

        sentences = cleaner_summary.split('. ')
        self.non_headline = '. '.join(sentences[2:])
        hashtag = (
            f"#{self.data_for_post['storm_name']}"
            if self.data_for_post['storm_type']
            not in ('Potential Tropical Cyclone', 'Tropical Depression')
            else ''
        )
        ### F String
        self.post_content = (
            f"{sentences[0].strip()}.\n\n"
            f"{sentences[1].strip()}.\n\n"
            f"{self.non_headline}\n\n"
            f"Track: {self.data_for_post['graphic_link']}\n"
            f"Advisory {self.data_for_post['advisory_number']}: {self.data_for_post['full_advisory_link']}\n\n"
            f"{hashtag}"
        )

    def make_alt_text(self):
        """create alt text for png"""
        return '\n'.join([self.data_for_post['summary_title'], self.non_headline])

    def post_to_mastodon(self):
        """Use data to post to Mastodon instance"""
        m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
        med_dict = m.media_post(
            self.data_for_post['graphic_data'],
            mime_type='image/png',
            description=self.make_alt_text(),
        )
        out = m.status_post(self.post_content, media_ids=med_dict)
        return (
            f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
        )
