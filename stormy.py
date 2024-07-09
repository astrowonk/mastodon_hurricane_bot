import re
from bs4 import BeautifulSoup
import requests
from html2text import html2text
from config import API_TOKEN
from mastodon import Mastodon
import hashlib
from time import sleep
from utils import (
    print_to_slack,
    json_write,
    write_new_status_data,
    get_storm_data,
    check_storm_guid_change,
)
import datetime

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
    def __init__(self, data_list, use_update=False):
        """Inited with a list of 6 dictionaries created by process_item and make_list_of_storms"""
        # assert len(data_list) == 6, 'data set must be length 6'
        self.data_list = data_list
        self.use_update = use_update
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
        self.storm_code = re.search(r'\((.+)\)', self.data_for_post['summary_title']).group(1)

        pattern = r'(.+) (\S+) Public Advisory Number (.+)$'
        rem = re.match(pattern, self.data_for_post['full_advisory_title'])
        self.data_for_post['advisory_number'] = rem.group(3)
        self.data_for_post['storm_type'] = rem.group(1)
        self.data_for_post['storm_name'] = rem.group(2).strip()

        if self.data_list[5]['title'].endswith('Update Statement'):
            if self.use_update:
                self.data_for_post['update_link'] = self.data_list[5]['link']
                self.data_for_post['update_title'] = self.data_list[5]['title']
            soup = BeautifulSoup(self.data_list[6]['description'], 'html.parser')
        else:
            soup = BeautifulSoup(self.data_list[5]['description'], 'html.parser')
        img_soup = soup.find('img')

        self.graphic_url = img_soup['src']
        self.data_for_post['graphic_link'] = soup.find('a')['href']

        pattern = r'_sm2\.png$'
        # change url so we can not use the small image, but a higher resolution one.
        if self.graphic_url:
            self.graphic_url = re.sub(pattern=pattern, repl='.png', string=self.graphic_url)
        self.make_graphic_data()

    def make_graphic_data(self):
        if not self.graphic_url:
            return
        r = requests.get(
            self.graphic_url, verify=VERIFY, headers={'Cache-Control': 'no-cache'}
        )
        self.data_for_post['graphic_data'] = r.content
        self.data_for_post['graphic_headers'] = dict(r.headers)
        self.data_for_post['graphic_hash'] = hashlib.md5(
            self.data_for_post['graphic_data']
        ).hexdigest()
        print_to_slack(str(self.data_for_post['graphic_headers']))

    def make_post_content(self):
        """with the data dictionary, create the text for the post."""
        # Use re.sub() to remove the ellipsis and replace with the captured text and a single period
        pattern = r'\.\.\.(.*?)\.\.\.'
        cleaner_summary = re.sub(pattern, r'\1.', self.data_for_post['summary'])
        title = ''
        sentences = cleaner_summary.split('. ')
        self.non_headline = '. '.join(sentences[2:])
        hashtag = (
            f"#{self.data_for_post['storm_name']}"
            if self.data_for_post['storm_type']
            not in ('Potential Tropical Cyclone', 'Tropical Depression')
            else ''
        )
        ### F String
        if self.data_for_post.get('update_link'):
            links = f"Update: {self.data_for_post['update_link']}\n\n"
            title = self.data_for_post['update_title'] + '\n\n'
        else:
            links = (
                f"Track: {self.data_for_post.get('graphic_link')}\n"
                f"Advisory {self.data_for_post['advisory_number']}: {self.data_for_post['full_advisory_link']}\n\n"
            )

        self.post_content = (
            f'{title}'
            f'{sentences[0].strip()}.\n\n'
            f'{sentences[1].strip()}.\n\n'
            f'{self.non_headline}\n\n'
            f'{links}'
            f'{hashtag}'
        )

    def run(self, force_update=False, no_post=False):
        old_data = get_storm_data(self.data_for_post)
        if check_storm_guid_change(self.data_for_post) or force_update:
            if not no_post:
                print_to_slack('Posting to Mastodon.')
                print_to_slack(f"Guid for storm {self.data_for_post['summary_guid']}")
                p_bool, p_status = self.post_to_mastodon(
                    verify_image_hash=old_data.get('graphic_hash')
                )
                if p_bool:
                    print_to_slack(p_status)
                    del self.data_for_post['graphic_data']
                    storm_id = self.data_for_post['storm_id']
                    json_write(self.data_for_post, f'{storm_id}_full_post_data.json')
                else:
                    print_to_slack(p_status, error=True)
            else:
                print_to_slack(
                    f'Posting disabled. Sending post content to log. Length: {len(self.post_content)}'
                )
                print_to_slack(self.post_content)

        else:
            print_to_slack(
                f"Summary for storm {self.data_for_post['storm_id']} unchanged at {datetime.datetime.now().isoformat()}"
            )
            print_to_slack('No posting to Mastodon')

    def make_alt_text(self):
        """create alt text for png"""
        return '\n'.join([self.data_for_post['summary_title'], self.non_headline])

    def should_check_image(self, verify_image_hash):
        return verify_image_hash and not self.data_for_post.get('update_title')

    def post_to_mastodon(self, verify_image_hash=None):
        """Use data to post to Mastodon instance"""
        use_image = True
        if self.data_for_post.get('update_title'):
            print_to_slack(
                f'This appears to be an update - {self.data_for_post.get("update_title")} No image.'
            )
            use_image = False
        elif verify_image_hash:
            print_to_slack(
                f"Checking image hash {verify_image_hash} vs {self.data_for_post['graphic_hash']} "
            )
            attempts = 1
            while attempts < 3:
                if verify_image_hash == self.data_for_post['graphic_hash']:
                    print_to_slack(
                        f'Image data is identical with hash {verify_image_hash}. Sleeping and retrying. Attempt {attempts}'
                    )
                    sleep(60)
                    self.make_graphic_data()
                    attempts = attempts + 1
                else:
                    break
            if verify_image_hash == self.data_for_post['graphic_hash']:
                return False, 'Failed to post due to duplicate image data'
        else:
            print_to_slack('Image verification disabled, no hash to check')

        m = Mastodon(access_token=API_TOKEN, api_base_url='https://vmst.io')
        if self.data_for_post.get('graphic_data') and use_image:
            med_dict = m.media_post(
                self.data_for_post['graphic_data'],
                mime_type='image/png',
                description=self.make_alt_text(),
            )
            out = m.status_post(self.post_content, media_ids=med_dict)
        else:
            out = m.status_post(self.post_content)
        return True, (
            f"Succesfully posted post id {out['id']} at {out['created_at']}. URL: {out['url']}"
        )
