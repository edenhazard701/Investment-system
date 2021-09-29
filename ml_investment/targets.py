import numpy as np
import pandas as pd
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
from typing import List, Tuple, Callable
from .data import SF1Data





class QuarterlyTarget:
    '''
    Calculator of target represented as column in quarter-based data.
    Work with quarterly slices of company.
    '''
    def __init__(self, col: str, quarter_shift: int=0):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, revenue)
        quarter_shift:
            number of quarters to shift. 
            e.g. if ``quarter_shift = 0`` than value for current quarter 
            will be returned. 
            If ``quarter_shift = 1`` than value for next quarter 
            will be returned.
            If ``quarter_shift = -1`` than value for previous quarter 
            will be returned.
        '''
        self.col = col
        self.quarter_shift = quarter_shift
        self._data_loader = None
        
        
    def _single_ticker_target(self, 
                              ticker_and_dates: Tuple[str,
                                                      List]) -> pd.DataFrame:
        ticker, dates = ticker_and_dates
        quarterly_data = self._data_loader.load_quarterly_data([ticker])[::-1]
        quarter_dates = quarterly_data['date'].astype(np.datetime64).values
        vals = []
        for date in dates:
            assert np.datetime64(date) in quarter_dates
            curr_date_mask = quarter_dates == np.datetime64(date)
            curr_quarter_idx = np.where(curr_date_mask)[0][0]
            idx = curr_quarter_idx + self.quarter_shift
            if idx >= 0 and idx < len(quarterly_data):
                value = quarterly_data[self.col].values[idx]
            else:
                value = np.nan
                
            vals.append(value)

        result = pd.DataFrame()
        result['y'] = vals
        result['date'] = dates
        result['ticker'] = ticker

        return result        
        

    def calculate(self, data_loader, info_df: pd.DataFrame,
                  n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''     
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_quarterly_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for. 
            Should have columns: ``["ticker", "date"]``               
        n_jobs:
            number of threads
                      
        Returns
        -------
        pd.DataFrame 
            targets having 'y' column
        '''
        self._data_loader = data_loader
        grouped = info_df.groupby('ticker')['date'].apply(lambda x:
                  x.tolist()).reset_index()
        params = [(ticker, dates) for ticker, dates in grouped.values]

        p = Pool(n_jobs)
        result = []
        for ticker_result in tqdm(p.imap(self._single_ticker_target, params)):
            result.append(ticker_result)

        result = pd.concat(result, axis=0)
        result = result.drop_duplicates(['ticker', 'date'])
        result = pd.merge(info_df, result, on=['ticker', 'date'], how='left')
        result = result.set_index(['ticker', 'date'])
        result = result.infer_objects()
        
        return result


class QuarterlyDiffTarget:
    '''
    Calculator of target represented as difference between column values
    in current and previous quarter.
    Work with quarterly slices of company.
    '''
    def __init__(self, col: str, norm: bool=True):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, revenue)
        norm:
            normalize difference to previous quarter or not
        '''
        self.curr_target = QuarterlyTarget(col=col, quarter_shift=0)
        self.last_target = QuarterlyTarget(col=col, quarter_shift=-1)
        self.norm = norm

    
    def calculate(self, data_loader, info_df: pd.DataFrame, 
                  n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''     
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_quarterly_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for. 
            Should have columns: ``["ticker", "date"]``               
        n_jobs:
            number of threads

        Returns
        -------
        pd.DataFrame
            targets having 'y' column
        '''
        curr_df = self.curr_target.calculate(data_loader, info_df, n_jobs)
        last_df = self.last_target.calculate(data_loader, info_df, n_jobs)
        curr_df['y'] = curr_df['y'] - last_df['y']
        if self.norm:
            curr_df['y'] = curr_df['y'] / np.abs(last_df['y'])

        return curr_df


class QuarterlyBinDiffTarget:
    '''
    Calculator of target represented as binary difference 
    between column values in current and previous quarter.
    Work with quarterly slices of company.
    '''
    def __init__(self, col):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, revenue)
        '''
        self.target = QuarterlyDiffTarget(col=col, norm=False)
    
    def calculate(self, data_loader, info_df: pd.DataFrame, n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_quarterly_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for.
            Should have columns: ``["ticker", "date"]``               
        n_jobs:
            number of threads

        Returns
        -------
        ``pd.DataFrame``
            targets having 'y' column
        '''
        target_df = self.target.calculate(data_loader, info_df, n_jobs)
        target_df.loc[target_df['y'].isnull() == False, 'y'] = \
            target_df.loc[target_df['y'].isnull() == False, 'y'] > 0
        target_df['y'] = target_df['y'].astype(float)
        
        return target_df




class DailyAggTarget:
    '''
    Calculator of target represented as aggregation function of daily values.
    Work with daily slices of company.
    '''
    def __init__(self, col: str, horizon: int=100, foo: Callable=np.mean):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, pe)
        horizon:
            number of days for target calculation.
            If ``horizon > 0`` than values will be get 
            from the future of current date.
            If ``horizon < 0`` than values will be get 
            from the past of current date
        foo:
            function processing target aggregation
        '''
        self.col = col
        self.horizon = horizon
        self.foo = foo
        self._data_loader = None
        
        
    def _single_ticker_target(self, 
                              ticker_and_dates: Tuple[str,
                                                      List]) -> pd.DataFrame:
        ticker, dates = ticker_and_dates
        result = pd.DataFrame()
        result['date'] = dates
        result['ticker'] = ticker
        result['y'] = None

        daily_data = self._data_loader.load_daily_data([ticker])
        if daily_data is None:
            return result
        daily_data = daily_data[::-1]
        daily_dates = daily_data['date'].astype(np.datetime64).values
        vals = []
        for date in dates:
            if self.horizon >= 0:
                series = daily_data[daily_dates >= np.datetime64(date)]
                series = series[self.col].values[:self.horizon]
            else:
                series = daily_data[daily_dates < np.datetime64(date)]
                series = series[self.col].values[self.horizon:]                
                               
            vals.append(self.foo(series.astype(float)))

        result['y'] = vals

        return result        
        

    def calculate(self, data_loader, info_df: pd.DataFrame, 
                  n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_daily_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for.
            Should have columns: ``["ticker", "date"]``               
        n_jobs:
            number of threads

        Returns
        -------
        ``pd.DataFrame``
            targets having 'y' column
        '''
        self._data_loader = data_loader
        grouped = info_df.groupby('ticker')['date'].apply(lambda x:
                  x.tolist()).reset_index()
        params = [(ticker, dates) for ticker, dates in grouped.values]

        p = Pool(n_jobs)
        result = []
        for ticker_result in tqdm(p.imap(self._single_ticker_target, params)):
            result.append(ticker_result)

        result = pd.concat(result, axis=0)
        result = result.drop_duplicates(['ticker', 'date'])
        result = pd.merge(info_df, result, on=['ticker', 'date'], how='left')
        result = result.set_index(['ticker', 'date'])
        
        return result


class DailySmoothedQuarterlyDiffTarget:
    '''
    Feature calculator getting difference between current and last quarter
    smoothed daily column values. Work with company quarter slices.
    '''
    def __init__(self, col: str, smooth_horizon: int=30, norm: bool=True):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, pe)
        smooth_horizon:
            number of days for target calculation.
            If ``smooth_horizon > 0`` than values for smoothing wiil be get 
            from future of quarter date.
            If ``smooth_horizon < 0`` than values for smoothing will be get 
            from the past of quarter date
        norm:
            normalize result or not
        '''

        self.norm = norm
        self.daily_target = DailyAggTarget(col=col, horizon=smooth_horizon,
                                           foo=np.mean)
        self.last_date_target = QuarterlyTarget(col='date', quarter_shift=-1)

    def calculate(self, data_loader, info_df: pd.DataFrame, 
                  n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_daily_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for. 
            Should have columns: ``["ticker", "date"]``               
        n_jobs:
            number of threads

        Returns
        -------
        ``pd.DataFrame``
            targets having 'y' column
        '''
        last_date_df = self.last_date_target.calculate(data_loader, info_df)
        last_date_df = last_date_df.reset_index()
        last_date_df['date'] = last_date_df['y']
        del last_date_df['y']

        curr_df = self.daily_target.calculate(data_loader, info_df)
        last_df = self.daily_target.calculate(data_loader, last_date_df)

        result = curr_df.copy()
        result['y'] = (curr_df['y'].values - last_df['y'].values)
        if self.norm:
            result['y'] = result['y'].values / last_df['y'].values

        return result




class ReportGapTarget:
    '''
    Calculator of target represented as gap at the quarter report date.
    Work with quarterly slices of company.
    '''
    def __init__(self, col: str, smooth_horizon: int=1, norm: bool=True):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like marketcap, pe)
        smooth_horizon:
            number of days for column smoothing
        norm:
            normalize gap value or not
        '''
        self.curr_target = DailyAggTarget(col=col, 
                                          horizon=smooth_horizon,
                                          foo = np.mean)

        self.last_target = DailyAggTarget(col=col, 
                                          horizon=-smooth_horizon,
                                          foo = np.mean)
        self.norm = norm
        
        
    def calculate(self, data_loader, info_df: pd.DataFrame, 
                  n_jobs: int = cpu_count()) -> pd.DataFrame:
        '''     
        Interface to calculate targets for dates and tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class implements ``load_daily_data(tickers: List[str])`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers and dates
            to calculate targets for. 
            Should have columns: ``["ticker", "date"]``             
        n_jobs:
            number of threads

        Returns
        -------
        ``pd.DataFrame``
            targets having 'y' column
        '''        
        
        curr_df = self.curr_target.calculate(data_loader, info_df, n_jobs)
        last_df = self.last_target.calculate(data_loader, info_df, n_jobs)
        curr_df['y'] = curr_df['y'] - last_df['y']
        if self.norm:
            curr_df['y'] = curr_df['y'] / np.abs(last_df['y'])

        return curr_df        
        
        
        
class BaseInfoTarget:
    '''
    Calculator of target represented by base company information
    '''
    def __init__(self, col: str):
        '''     
        Parameters
        ----------
        col:
            column name for target calculation(like sector, industry)
        '''
        self.col = col
        
        
    def calculate(self, data_loader, info_df: pd.DataFrame) -> pd.DataFrame:
        '''     
        Interface to calculate targets for tickers in info_df
        based on data from data_loader
        
        Parameters
        ----------
        data_loader:
            class ``implements load_base_data()`` 
            ``-> pd.DataFrame`` interface
        info_df:
            ``pd.DataFrame`` containing information of tickers
            to calculate targets for.
            Should have columns: ``["ticker"]``               

        Returns
        -------
        ``pd.DataFrame``
            targets having 'y' column
        '''        
        base_df = data_loader.load_base_data()[['ticker', self.col]]
        result = pd.merge(info_df, base_df, on='ticker', how='left')
        result = result.rename({self.col: 'y'}, axis=1)
        result = result[['ticker', 'y']]
        result = result.set_index(['ticker'])

        return result             
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        













