import argparse
from ml_investment.download import YahooDownloader
from ml_investment.utils import load_tickers



def main(data_path:str=None):
    '''
    Download quarterly and base data from https://finance.yahoo.com

    Parameters
    ----------
    data_path:
        path to folder in which downloaded data will be stored.
        OR ``None`` (downloading path will be as ``yahoo_data_path`` from 
        `~/.ml_investment/config.json`
    '''
    if data_path is None:
        config = load_config()
        data_path = config['yahoo_data_path']

    tickers = load_tickers()['base_us_stocks']
    downloader = YahooDownloader()
    downloader.download_quarterly_data(data_path, tickers)
    downloader.download_base_data(data_path, tickers)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    arg = parser.add_argument
    arg('--data_path', type=str)
    args = parser.parse_args()
    main(args.data_path)
 
