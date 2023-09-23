# Tropical Updates to Mastodon

This grabs the [NHC Atlantic RSS Feed](https://www.nhc.noaa.gov/aboutrss.shtml), specifically "Atlantic Basin Tropical Cyclones" from `https://www.nhc.noaa.gov/index-at.xml` and generates automated posts to a Mastodon bot with this data.

Caveats are that there are no test RSS feeds that have 0 or 2 storms at the same time during Hurricane season, so there will be some failure modes that I'll address as the 2023 season winds down.

