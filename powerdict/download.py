# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01-source-data.ipynb (unless otherwise specified).

__all__ = ['retrieve_opsd_power_plants_page', 'extract_EU_power_plants_csv_url', 'download_opsd_power_plants_data']

# Cell
import pandas as pd
import numpy as np

import requests
from bs4 import BeautifulSoup as bs

# Cell
def retrieve_opsd_power_plants_page(opsd_root='https://data.open-power-system-data.org'):
    page_url = f'{opsd_root}/conventional_power_plants/2020-10-01'
    r = requests.get(page_url)

    return r

# Cell
def extract_EU_power_plants_csv_url(r, opsd_root='https://data.open-power-system-data.org'):
    soup = bs(r.content)
    csv_url = opsd_root + '/' + soup.find('a', string='conventional_power_plants_EU.csv')['href']

    return csv_url

# Cell
def download_opsd_power_plants_data(raw_data_dir='../data/raw'):
    r = retrieve_opsd_power_plants_page()
    csv_url = extract_EU_power_plants_csv_url(r)

    df_OPSD = pd.read_csv(csv_url)
    df_OPSD.to_csv(f'{raw_data_dir}/OPSD.csv', index=False)