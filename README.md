# Tropical Weather (Atlantic) Updates to Mastodon

## This Mastodon bot is posting during hurricane system [hosted on vmst.io](https://vmst.io/@nhc_atlantic_bot).

This grabs the [NHC Atlantic RSS Feed](https://www.nhc.noaa.gov/aboutrss.shtml), specifically "Atlantic Basin Tropical Cyclones" from `https://www.nhc.noaa.gov/index-at.xml` and generates automated posts to a Mastodon bot with this data.

There are a few functions in the `nhc_bot.py` script that parse the feed into storm-specific lists of 6-7 items per storm, using `lxml`.

The `Stormy` class then takes a list of dictionaries for one storm, and generates text, links, and images for a Mastodon post.

Some somewhat messy condition logic is needed to figure out "Is this an update?." The main script first checks the `etag` of the rss feed itself,  from the http headers. If it has changed, the feed is parsed into storm lists and each `Stormy` instance is checked against the last post information (written to JSON), to see if the summary text changed. 

Finally, before posting, a hash of the image bytes is checked against the hash of the last posted track image, since sometimes the image data lags behind the RSS feed, and I don't want to post a 2PM image with the 5PM update.

