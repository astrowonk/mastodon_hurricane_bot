from nhc_bot import make_list_of_storms, process_url
import unittest
from stormy import Stormy, Summary


class TestFunctions(unittest.TestCase):
    def test_pipeline(self):
        """This should be broken up into more tests; something is better than nothing."""
        with open('two_storm_example.xml', 'rb') as f:
            some_bytes = f.read()

        out = process_url(text=some_bytes)
        self.assertTrue(len(out) == 14)
        self.assertEqual(
            out[0]['guid'], 'https://www.nhc.noaa.gov/gtwo.php?basin=atlc&202309232346'
        )

        thelist = make_list_of_storms(out)
        print(thelist)
        self.assertEqual(len(thelist[0]), 7)

        self.assertEqual(len(thelist[1]), 6)

        s = Stormy(thelist[0])
        self.assertEqual(s.storm_code, 'AT1/AL162023')
        self.assertEqual(s.post_content[:7], 'OPHELIA')

        thesummary = Summary(out[0])
        self.assertEqual(thesummary.summary_dict['title'], 'Atlantic Tropical Weather Outlook')

    def test_potential_storm(self):
        """This should be broken up into more tests; something is better than nothing."""
        with open('example-potential-storm.xml', 'rb') as f:
            some_bytes = f.read()

        out = process_url(text=some_bytes)

        thelist = make_list_of_storms(out)
        print(thelist)
        self.assertEqual(len(thelist[0]), 9)

        s = Stormy(thelist[0])
        self.assertEqual(s.storm_code, 'AT1/AL012024')
        print(s.post_content)
        self.assertEqual(s.data_for_post['storm_type'], 'Potential Tropical Cyclone')

        # no hashtag
        self.assertEqual(s.post_content.split('\n\n')[-1], '')

    def test_update_storm(self):
        with open('weird_xml_update_2_storms.xml', 'rb') as f:
            some_bytes = f.read()

        out = process_url(text=some_bytes)
        list_of_storms = make_list_of_storms(out)
        s = Stormy(list_of_storms[0], use_update=True)
        self.assertTrue(s.post_content.startswith('Hurricane Beryl Update Statement'))
        s = Stormy(list_of_storms[0], use_update=False)
        self.assertTrue(s.post_content.startswith('EYEWALL OF EXTREMELY DANGEROUS CATEGORY 4'))

    def test_no_storm(self):
        with open('no_storm.xml', 'rb') as f:
            some_bytes = f.read()
        out = process_url(text=some_bytes)
        list_of_storms = make_list_of_storms(out)
        self.assertEqual(len(list_of_storms), 0)
