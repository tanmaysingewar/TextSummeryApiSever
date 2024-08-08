import requests
import json
import random

def get_proxy():
    url = 'https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=protocolipport&format=json&timeout=20000&limit=10'
    response = requests.get(url)
    print(response)
    random_no = random.randint(0, 9)
    print(random_no)
    return response.json()['proxies'][random_no]['proxy']

__all__ = ['get_proxy']