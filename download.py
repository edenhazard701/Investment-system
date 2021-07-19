import os
import requests
import time
import numpy as np
import copy
from tqdm import tqdm
from multiprocessing import Pool
from itertools import repeat
from utils import load_json, save_json




class QuandlDownloader:
    def __init__(self, config, secrets, retry_cnt=10, sleep_time=0.2):
        self.config = config
        self.secrets = secrets
        self.retry_cnt = retry_cnt
        self.sleep_time = sleep_time
        self._save_dirpath = None
        self._base_url_route = None
                

    def _form_quandl_url(self, route):
        url = "{}/{}&api_key={}".format(
                self.config['quandl_api_url'],
                route, self.secrets['quandl_api_key'])
                
        return url 


    def _batch_ticker_download(self, ticker_list):
        time.sleep(self.sleep_time)
        url = self._base_url_route.format(ticker=','.join(ticker_list))
        url = self._form_quandl_url(url)
        response = requests.get(url)
        if response.status_code != 200:
            return
        data = response.json()
        datatable_data = np.array(data['datatable']['data'])
        ticker_seq = np.array([x[0] for x in data['datatable']['data']])
        
        curr_data = copy.deepcopy(data)
        curr_data['datatable']['data'] = []

        for ticker in ticker_list:
            curr_datatable_data = datatable_data[ticker_seq == ticker].tolist()
            curr_data['datatable']['data'] = curr_datatable_data

            save_filepath = '{}/{}.json'.format(self._save_dirpath, ticker)
            save_json(save_filepath, curr_data)            

            
    def ticker_download(self, base_url_route, ticker_list, save_dirpath,
                 skip_exists=False, batch_size=10, n_jobs=12):
        self._save_dirpath = save_dirpath
        self._base_url_route = base_url_route
        os.makedirs(save_dirpath, exist_ok=True)
        if skip_exists:
            exist_tickers = [x.split('.')[0] for x in os.listdir(save_dirpath)]
            ticker_list = list(set(ticker_list).difference(set(exist_tickers)))
        
        batches = [ticker_list[k:k+batch_size] 
                        for k in range(0, len(ticker_list), batch_size)]
        p = Pool(n_jobs)
        for _ in tqdm(p.imap(self._batch_ticker_download, batches)):
            None
            
            
            
class TinkoffDownloader:
    def __init__(self, secrets):
        self.headers = {"Authorization": 
                        "Bearer {}".format(secrets['tinkoff_token'])}
        
        def get_stocks(self)
            url = 'https://api-invest.tinkoff.ru/openapi/market/stocks'
            response = requests.get(url, headers=self.headers)
            result = response.json()        
            
            return result
            
            
        def get_portfolio(self):
            url = 'https://api-invest.tinkoff.ru/openapi/portfolio' \
                   '?brokerAccountId={}'
            url = url.format(self.secrets['tinkoff_broker_account_id'])
            response = requests.get(url, headers=self.headers)
            portfolio = response.json()
            
            return tinkoff_portfolio['payload']['positions']
            
            
        def get_figi_by_ticker(self, ticker):
            url = 'https://api-invest.tinkoff.ru/' \ 
                  'openapi/market/search/by-ticker?ticker={}'.format(ticker)
            response = requests.get(url, headers=self.headers)
            figi = response.json()['payload']['instruments'][0]['figi']            
        
            return figi
        
            
        def get_price(self, ticker):
            figi = self.get_figi_by_ticker(ticker)      
            url = 'https://api-invest.tinkoff.ru/openapi/market/candles' \
                  '?figi={}&from={}&to={}&interval=day'

            end = np.datetime64('now')
            end = str(end) + '%2B00%3A00'
            start = np.datetime64('now') - np.timedelta64(7, 'D')
            start = str(start) + '%2B00%3A00'
            
            url = url.format(figi, start, end)

            response = requests.get(url, headers=self.headers)
            close_price = response.json()['payload']['candles'][-1]['c']
            
            return close_price
            

def get_tinkoff_portfolio(secrets):
    headers = {"Authorization": "Bearer {}".format(secrets['tinkoff_token'])}
    url = 'https://api-invest.tinkoff.ru/openapi/portfolio?brokerAccountId=2001883988'
    response = requests.get(url, headers=headers)
    tinkoff_portfolio = response.json()
    
    return tinkoff_portfolio['payload']['positions']


def get_tinkoff_tickers(secrets):
    headers = {"Authorization": "Bearer {}".format(secrets['tinkoff_token'])}
    url = 'https://api-invest.tinkoff.ru/openapi/market/stocks'
    response = requests.get(url, headers=headers)
    result = response.json()
    tickers = [x['ticker'] for x in result['payload']['instruments']]
    
    return tickers


def get_tinkoff_price(ticker, secrets):
    headers = {"Authorization": "Bearer {}".format(secrets['tinkoff_token'])}
    url = 'https://api-invest.tinkoff.ru/openapi/market/search/by-ticker?ticker={}'.format(ticker)
    response = requests.get(url, headers=headers)
    figi = response.json()['payload']['instruments'][0]['figi']
    
    price_url = 'https://api-invest.tinkoff.ru/openapi/market/candles?figi={}&from={}&to={}&interval=day'

    end = np.datetime64('now')
    start = np.datetime64('now') - np.timedelta64(7, 'D')

    price_url = price_url.format(figi, str(start) + '%2B00%3A00', str(end) + '%2B00%3A00')

    response = requests.get(price_url, headers=headers)
    val = response.json()['payload']['candles'][-1]['c']
    
    return val



























































