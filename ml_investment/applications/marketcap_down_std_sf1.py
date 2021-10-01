import argparse
import os
import lightgbm as lgbm
import catboost as ctb
from urllib.request import urlretrieve
from ml_investment.utils import load_config
from ml_investment.data import SF1Data, QuandlCommoditiesData, ComboData
from ml_investment.features import QuarterlyFeatures, BaseCompanyFeatures, \
                                   FeatureMerger, DailyAggQuarterFeatures, \
                                   QuarterlyDiffFeatures
from ml_investment.targets import DailyAggTarget
from ml_investment.models import TimeSeriesOOFModel, EnsembleModel, LogExpModel
from ml_investment.metrics import median_absolute_relative_error, down_std_norm
from ml_investment.pipelines import BasePipeline
from ml_investment.download_scripts import download_sf1, download_commodities


URL = 'https://github.com/fartuk/ml_investment/releases\
      /download/weights/marketcap_down_std_sf1.pickle'
OUT_NAME = 'marketcap_down_std_sf1'
CURRENCY = 'USD'
TARGET_HORIZON = 90
MAX_BACK_QUARTER = 20
BAGGING_FRACTION = 0.7
MODEL_CNT = 20
FOLD_CNT = 20
QUARTER_COUNTS = [2, 4, 10]
COMPARE_QUARTER_IDXS = [1, 4]
AGG_DAY_COUNTS = [100, 200, 400, 800]
SCALE_MARKETCAP = ["4 - Mid", "5 - Large", "6 - Mega"]
DAILY_AGG_COLUMNS = ["marketcap", "pe"]
CAT_COLUMNS = ["sector", "sicindustry"]
QUARTER_COLUMNS = [
            "revenue",
            "netinc",
            "ncf",
            "assets",
            "ebitda",
            "debt",
            "fcf",
            "gp",
            "workingcapital",
            "cashneq",
            "rnd",
            "sgna",
            "ncfx",
            "divyield",
            "currentratio",
            "netinccmn"
         ]



class MarketcapDownStdSF1:
    '''
    Model is used to predict future down-std value.
    Pipeline consist of time-series model training( 
    :class:`~ml_investment.models.TimeSeriesOOFModel` )
    and validation on real marketcap down-std values(
    :class:`~ml_investment.targets.DailyAggTarget` ).
    Model prediction may be interpreted as "risk" for the next quarter.
    :class:`~ml_investment.data.SF1Data`
    is used for loading data.

    Note:
        SF1 dataset is paid, so for using this model you need to subscribe 
        and paste quandl token to `~/.ml_investment/secrets.json`
        ``quandl_api_key``
    '''
    def __init__(self, pretrained=True):
        '''
        Parameters
        ----------
        pretrained:
            use pretreined weights or not. If so,
            `marketcap_down_std_sf1.pickle` will be downloaded. 
            Downloading directory path can be changed in
            `~/.ml_investment/config.json` ``models_path``
        '''
        self.config = load_config()

        self._check_download_data()
        self.data_loader = self._create_loader()
        self.pipeline = self._create_pipeline()   
        
        core_path = '{}/{}.pickle'.format(self.config['models_path'],
                                          OUT_NAME)

        if pretrained:
            if not os.path.exists(core_path):
                urlretrieve(URL, core_path)       
            self.pipeline.load_core(core_path)


    def _check_download_data(self):
        if not os.path.exists(self.config['sf1_data_path']):
            print('Downloading sf1 data')
            download_sf1.main()
 

    def _create_loader(self):
        data_loader = SF1Data(self.config['sf1_data_path'])
        return data_loader 


    def _create_pipeline(self):
        fc1 = QuarterlyFeatures(columns=QUARTER_COLUMNS,
                                quarter_counts=QUARTER_COUNTS,
                                max_back_quarter=MAX_BACK_QUARTER)

        fc2 = BaseCompanyFeatures(cat_columns=CAT_COLUMNS)
            
        fc3 = QuarterlyDiffFeatures(columns=QUARTER_COLUMNS,
                                    compare_quarter_idxs=COMPARE_QUARTER_IDXS,
                                    max_back_quarter=MAX_BACK_QUARTER)
        
        fc4 = DailyAggQuarterFeatures(columns=DAILY_AGG_COLUMNS,
                                      agg_day_counts=AGG_DAY_COUNTS,
                                      max_back_quarter=MAX_BACK_QUARTER)


        feature = FeatureMerger(fc1, fc2, on='ticker')
        feature = FeatureMerger(feature, fc3, on=['ticker', 'date'])
        feature = FeatureMerger(feature, fc4, on=['ticker', 'date'])

        target = DailyAggTarget(col='marketcap',
                                horizon=TARGET_HORIZON,
                                foo=down_std_norm)

        base_models = [LogExpModel(lgbm.sklearn.LGBMRegressor()),
                       LogExpModel(ctb.CatBoostRegressor(verbose=False))]
                       
        ensemble = EnsembleModel(base_models=base_models, 
                                 bagging_fraction=BAGGING_FRACTION,
                                 model_cnt=MODEL_CNT)

        model = TimeSeriesOOFModel(base_model=ensemble,
                                   time_column='date',
                                   fold_cnt=FOLD_CNT)

        pipeline = BasePipeline(feature=feature, 
                                target=target, 
                                model=model, 
                                metric=median_absolute_relative_error,
                                out_name=OUT_NAME)

        return pipeline


    def fit(self):
        '''     
        Interface to fit pipeline model. Pre-downloaded appropriate
        data will be used.
        ''' 
        tickers_df = self.data_loader.load_base_data(
            currency=CURRENCY,
            scalemarketcap=SCALE_MARKETCAP)
        ticker_list = tickers_df['ticker'].unique().tolist()
        result = self.pipeline.fit(self.data_loader, ticker_list)
        print(result)


    def predict(self, tickers):
        '''     
        Interface for model inference.
        
        Parameters
        ----------
        tickers:
            tickers of companies to make inference for
        ''' 
        return self.pipeline.execute(self.data_loader, tickers)





def main():
    '''
    Default model training. Resulted model weights directory path 
    can be changed in `~/.ml_investment/config.json` ``models_path``
    '''
    model = MarketcapDownStdSF1(pretrained=False)
    model.fit()
    path = '{}/{}'.format(model.config['models_path'], OUT_NAME)
    model.pipeline.export_core(path)    


if __name__ == '__main__':
   main() 
    
