
import os
from dateutil import  tz
TIME_ZONE = tz.gettz("Asia/Kolkata")
ENTER_SYMBOL = []
MASTER_LIST = None
SHOONAY_OBJ = None
RUN_PROCESS =True
ORDER_TAG = 'DFT_INTRA' 
FEED_JSON  = {}
ORDER_STATUS = {}
POSITION_JSON = {}
FEED_SYNTAX = []
WEEKLY_EXPIRY =None #  date(2022,9,1)
SYMBOL_TOKEN =None
IS_TEST = False
ACCESS_TOKEN =None
TOKEN_MAP = {}
SYM_MAP = {'NIFTY':('26000','NFO',1800,50 ,'NSE'),'BANKNIFTY':('26009','NFO',1800,100 ,'NSE'),'BSXOPT':('1','BFO',100,100 ,'BSE') ,'FINNIFTY':('26037','NFO',1800,50,'NSE')}   

# Flat-trade credentials (read from environment variables)
# Set these in your environment or in a local .env (never commit real values).
FIN_APIKEY = os.getenv('FIN_APIKEY', '')
FIN_SECRETKEY = os.getenv('FIN_SECRETKEY', '')
FIN_TOTP_TOKEN = os.getenv('FIN_TOTP_TOKEN', '')
FIN_PWD = os.getenv('FIN_PWD', '')
FIN_USER = os.getenv('FIN_USER', '')



ENTRY_TIME = (9,17,0)
EXIT_TIME = (15,25,0)
EMA_EXIT_TIME = (14,30,0)
ORDER_TYPE ='I'    #  I -> intraday M-> margin


TOKEN_PATH = os.getenv('TOKEN_PATH', 'token.json')
BOT_CHAT_ID = os.getenv('BOT_CHAT_ID', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
SCAN_INTERVAL =  1 # in seconds
EXCHANGE = 'NFO' #BFO or NFO
SYM_CONFIG = {'NIFTY':     {'enable':True,'exch':'NFO', 'qty':1,'sellDelta':0.15,  'buyStrike':500,  'mtmSLprcnt':0.5 ,'margin':200000},
              'BANKNIFTY': {'enable':False,'exch':'NFO', 'qty':1,'sellDelta':0.15,  'buyStrike':500,  'mtmSLprcnt':0.5 ,'margin':200000}
            }

EMA_LENGTH =  14
TRADE_TIMEFRAME = 5
EXIT_BUFFER = 1
IS_ENTRY_ON_CROSS = False


    
