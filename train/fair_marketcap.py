import argparse
import lightgbm as lgbm
import catboost as ctb
from utils import load_json
from data import SF1Data
from features import QuarterlyFeatures, BaseCompanyFeatures, FeatureMerger, \
                     DailyAggQuarterFeatures
from targets import QuarterlyTarget
from models import GroupedOOFModel, EnsembleModel, LogExpModel
from metrics import median_absolute_relative_error
from pipelines import BasePipeline


SAVE_PATH = 'models_data/fair_marketcap'
OUT_NAME = 'fair_marketcap'
CURRENCY = 'USD'
MAX_BACK_QUARTER = 10
BAGGING_FRACTION = 0.7
MODEL_CNT = 20
FOLD_CNT = 5
QUARTER_COUNTS = [2, 4, 10]
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

if __name__ == '__main__':
    config = load_json('config.json')
    data_loader = SF1Data(config['sf1_data_path'])
    tickers_df = data_loader.load_base_data(
        currency=CURRENCY,
        scalemarketcap=SCALE_MARKETCAP)
    ticker_list = tickers_df['ticker'].unique().tolist()

    fc1 = QuarterlyFeatures(
        columns=QUARTER_COLUMNS,
        quarter_counts=QUARTER_COUNTS,
        max_back_quarter=MAX_BACK_QUARTER)

    fc2 = BaseCompanyFeatures(cat_columns=CAT_COLUMNS)

    # Daily agss on marketcap and pe is possible here because it 
    # normalized and there are no leakage.
    fc3 = DailyAggQuarterFeatures(
        columns=DAILY_AGG_COLUMNS,
        agg_day_counts=AGG_DAY_COUNTS,
        max_back_quarter=MAX_BACK_QUARTER)
    
    feature = FeatureMerger(fc1, fc2, on='ticker')
    feature = FeatureMerger(feature, fc3, on=['ticker', 'date'])

    target = QuarterlyTarget(col='marketcap', quarter_shift=0)

    base_models = [LogExpModel(lgbm.sklearn.LGBMRegressor()),
                   LogExpModel(ctb.CatBoostRegressor(verbose=False))]
                   
    ansamble = EnsembleModel(
        base_models=base_models, 
        bagging_fraction=BAGGING_FRACTION,
        model_cnt=MODEL_CNT)

    model = GroupedOOFModel(ansamble,
                            group_column='ticker',
                            fold_cnt=FOLD_CNT)

    pipeline = BasePipeline(feature=feature, 
                            target=target, 
                            model=model, 
                            metric=median_absolute_relative_error,
                            out_name=OUT_NAME)
                            
    result = pipeline.fit(data_loader, ticker_list)
    print(result)
    pipeline.export_core(SAVE_PATH)    
    
    
    
    
