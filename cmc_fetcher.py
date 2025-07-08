from dotenv import load_dotenv
import os
import json
import redis
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import requests
import pandas as pd

load_dotenv()

API_KEY = os.getenv("CMC_API_KEY")
url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': API_KEY}
params = {'start': '1', 'limit': '100', 'convert': 'USD'}
r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), username=os.getenv("REDIS_USERNAME"), password=os.getenv("REDIS_PASSWORD"),)


def fetch_data_app():
    
    if r.exists("CMC_DATA"):
        data = json.loads(r.get("CMC_DATA"))
    else:
        data = None

    if not data or len(data) <= 0:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()['data']

    return pd.DataFrame([{
        'Name': coin['name'],
        'Symbol': coin['symbol'],
        'Last Price': coin['quote']['USD']['price'],
        '24h Change (%)': coin['quote']['USD']['percent_change_24h'],
        '7d Change (%)': coin['quote']['USD']['percent_change_7d'],
        '30d Change (%)': coin['quote']['USD']['percent_change_30d'],
        '90d Change (%)': coin['quote']['USD']['percent_change_90d'],
        'Market Cap': coin['quote']['USD']['market_cap']
    } for coin in data])
    
