import json
import requests
from datetime import datetime, timezone, timedelta
import argparse
import logging
import os

import pandas as pd
from sodapy import Socrata


import utils


DATE_FORMAT_HUMANS = "%Y-%m-%d"
DATE_FORMAT_API = "%d/%m/%Y"
DATE_FORMAT_SOCRATA = "%Y-%m-%dT00:00:00.000"


DEVICES_ENDPOINT = (
    "https://www.eco-visio.net/api/aladdin/1.0.0/pbl/publicwebpageplus/89?withNull=true"
)

SO_WEB = os.getenv("SO_WEB")
SO_TOKEN = os.getenv("SO_TOKEN")
SO_USER = os.getenv("SO_USER")
SO_PASS = os.getenv("SO_PASS")

# Socrata dataset IDs
COUNTERS_DATASET = os.getenv("COUNTERS_DATASET")
DEVICE_DATASET = os.getenv("DEVICE_DATASET")


def handle_date_args(start_string, end_string):
    """Parse or set default start and end dates from CLI args.

    Args:
        start_string (string): Date (in UTC) of earliest records to be fetched (YYYY-MM-DD).
            Defaults to yesterday.
        end_string (string): Date (in UTC) of most recent records to be fetched (YYYY-MM-DD).
            Defaults to today.

    Returns:
        list: The start date and end date as python datetime objects
    """
    if start_string:
        # parse CLI arg date
        start_date = datetime.strptime(start_string, DATE_FORMAT_HUMANS).replace(
            tzinfo=timezone.utc
        )
    else:
        # create yesterday's date
        start_date = datetime.now(timezone.utc) - timedelta(days=1)

    if end_string:
        # parse CLI arg date
        end_date = datetime.strptime(end_string, DATE_FORMAT_HUMANS).replace(
            tzinfo=timezone.utc
        )
    else:
        # create today's date
        end_date = datetime.now(timezone.utc)

    start_date = start_date.strftime(DATE_FORMAT_API)
    end_date = end_date.strftime(DATE_FORMAT_API)

    return start_date, end_date


def get_count_data(device, start_date, end_date):
    """
    Goes to API and gets the data for one device ID

    Parameters
    ----------
    device : list
        The individual device metadata.
    start_date : String
        Start date for querying the data.
    end_date : String
        End date for querying the data.

    Returns
    -------
    device_df : Pandas DataFrame
        All of data retrived from this device.

    """

    mainid = device["idPdc"]
    name = device["nom"]

    additionalids = []

    url = f"https://www.eco-visio.net/api/aladdin/1.0.0/pbl/publicwebpageplus/data/{mainid}?idOrganisme=89&idPdc={mainid}&fin={end_date}&debut={start_date}&interval=4&flowIds="

    for related in device["pratique"]:
        # Each device has a series of secondary devices as well.
        flowid = related["id"]

        t = f"{flowid}%3B"

        url = f"{url}{t}"

        additionalids.append(t)

    url = url[: len(url) - 3]

    res = requests.get(url)

    count_data = json.loads(res.text)
    logger.debug(f"{len(count_data)} records found for {name}")

    if count_data:
        device_df = pd.DataFrame(count_data)
        device_df = device_df.rename(columns={0: "Date", 1: "Count"})
        device_df["Count"] = device_df["Count"].astype(int)
        device_df = device_df[device_df["Count"] > 0]
        device_df["Sensor ID"] = mainid
        device_df["Sensor Name"] = name
        device_df["Record ID"] = str(mainid) + device_df["Date"]
        return device_df
    else:
        return pd.DataFrame()


def to_socrata(df, soda):
    """
    Changes the dataframe's format before being sent to Socrata

    Parameters
    ----------
    df : Pandas Dataframe
        Data from the EcoCounters API.
    soda : SodaPy client object

    Returns
    -------
    None.

    """
    logger.debug(f"{len(df)} records being upsert to Socrata")
    df["Date"] = pd.to_datetime(df["Date"], infer_datetime_format=True)
    df["Date"] = df["Date"].dt.strftime(DATE_FORMAT_SOCRATA)

    payload = df.to_dict(orient="records")
    soda.upsert(COUNTERS_DATASET, payload)

def publish_device_data(soda, device_data):
    """
    Upserts data to the socrata dataset for the trail counter device metadata

    Args:
        soda: SodaPy client object
        device_data: Pandas dataframe
            Device metadata from the eco-counters API.

    Returns:
        None

    """
    output_fields = ["idPdc", "lat", "lon", "nom"]
    field_mapping = {
        "idPdc": "Sensor ID",
        "lat": "Latitude",
        "lon": "Longitude",
        "nom": "Sensor Name"
    }
    device_data = device_data[output_fields]
    device_data.rename(columns=field_mapping, inplace=True)
    soda.upsert(DEVICE_DATASET, device_data)

def main(args):
    # earliest start_date = "2014-02-26"
    soda = Socrata(SO_WEB, SO_TOKEN, username=SO_USER, password=SO_PASS, timeout=500,)

    # Gets the list of count devices from the API
    res = requests.get(DEVICES_ENDPOINT)
    devices_dict = json.loads(res.text)
    devices_data = pd.DataFrame(devices_dict)

    start_date, end_date = handle_date_args(args.start, args.end)

    for device in devices_dict:
        device_df = get_count_data(device, start_date, end_date)
        if not device_df.empty:
            to_socrata(device_df, soda)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        type=str,
        help=f"Date (in UTC) of earliest records to be fetched (YYYY-MM-DD). Defaults to yesterday",
    )

    parser.add_argument(
        "--end",
        type=str,
        help=f"Date (in UTC) of the most recent records to be fetched (YYYY-MM-DD). Defaults to today",
    )

    args = parser.parse_args()
    logger = utils.get_logger(__file__, level=logging.DEBUG)


main(args)
