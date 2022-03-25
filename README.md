# atd-ped-bike-crash

A repo for work related to the Austin Vision Zero team's project to analyze pedestrian and bicycle crashes. 

## Trail Counters Data

The City of Austin has deployed a number of devices that simply count the number of people who walk, bike, or roll by the sensor.

[This data can be explored graphically at this public website.](https://data.eco-counter.com/ParcPublic/?id=89#)

This script uses the public website's API to grab data for all of the devices and publish it to the city's open data portal.

### CLI Arguments

`python counter_data.py --start <start_date> --end <end_date>`

`--start` and `--end` are optional and will default to yesterday and today, respectively.