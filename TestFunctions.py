from nhc_bot import make_list_of_storms, process_url
import unittest
from stormy import Stormy


class TestFunctions(unittest.TestCase):

    def test_pipeline(self):
        """This should be broken up into more tests; something is better than nothing."""
        with open('two_storm_example.xml', 'rb') as f:
            some_bytes = f.read()

        out = process_url(text=some_bytes)
        self.assertTrue(len(out) == 14)
        self.assertEqual(
            out[0]['guid'],
            'https://www.nhc.noaa.gov/gtwo.php?basin=atlc&202309232346')

        thelist = make_list_of_storms(out)
        print(thelist)
        self.assertEqual(len(thelist[0]), 6)

        s = Stormy(thelist[0])
        self.assertEqual(s.storm_code, 'AT1/AL162023')
        self.assertEqual(s.post_content[:7], 'OPHELIA')
