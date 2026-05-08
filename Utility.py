import pandas as pd
import requests
import inspect
from datetime import datetime , timedelta , time
from urllib.parse import parse_qs,urlparse
import hashlib
from time import sleep,time as TT
import math
import config
from Logger import logger 
from NorenApi import  NorenApi
import pyotp
import json
from py_vollib.black_scholes.implied_volatility import implied_volatility
from py_vollib.black_scholes.greeks.analytical import delta


def getConfig():
    try:
        with open(config.TOKEN_PATH, 'r') as json_file:
            extractData = json.load(json_file)
            logger.info(f'Read config data : {extractData}')
            return extractData
    except :
        logger.error('Failed to read saved config')
    return {} 


def setConfig(updateDict):
    jconfig = getConfig()
    for key, value in updateDict.items():
        jconfig[key] = value
    jconfig['timestamp'] = datetime.now(config.TIME_ZONE).strftime('%Y-%m-%d')
    logger.info(f'Update config   {updateDict}')
    # write it back to the file
    with open(config.TOKEN_PATH, 'w') as f:
        json.dump(jconfig, f)

def isTokenValid():
    token = getConfig()
    config.SHOONAY_OBJ = NorenApi(host='https://piconnect.flattrade.in/PiConnectTP/', websocket='wss://piconnect.flattrade.in/PiConnectWSTp/')
    if token is not None and len(token) > 0  and 'accesstoken' in token:
        config.SHOONAY_OBJ.set_session(userid= config.FIN_USER, password = config.FIN_PWD, usertoken = token['accesstoken'])
        if config.SHOONAY_OBJ.get_quotes(exchange='BSE', token='1') is  not None: 
            logger.info(f'Token is valid ')
            return  token['accesstoken']



def FlatTradelogin():
    
    config.SHOONAY_OBJ = NorenApi(host='https://piconnect.flattrade.in/PiConnectTP/', websocket='wss://piconnect.flattrade.in/PiConnectWSTp/')
    storedToken = isTokenValid()
    if storedToken is not None:
        config.ACCESS_TOKEN = storedToken
        res = config.SHOONAY_OBJ.set_session(userid=config.FIN_USER, password=config.FIN_PWD, usertoken = config.ACCESS_TOKEN)
    else:
        headerJson =  {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36", "Referer":"https://auth.flattrade.in/"}
        sesUrl = 'https://authapi.flattrade.in/auth/session'
        passwordEncrpted =  hashlib.sha256(config.FIN_PWD.encode()).hexdigest()
        ses = requests.Session()

        res_pin = ses.post(sesUrl,headers=headerJson)
        sid = res_pin.text
        logger.info(f'sid {sid}')
        url2 = 'https://authapi.flattrade.in/ftauth'
        payload = {"UserName":config.FIN_USER,"Password":passwordEncrpted,"PAN_DOB":pyotp.TOTP(config.FIN_TOTP_TOKEN).now(),"App":"","ClientID":"","Key":"","APIKey":config.FIN_APIKEY,"Sid":sid,
                "Override":"","Source":"AUTHPAGE"}
        res2 = ses.post(url2, json=payload)
        reqcodeRes = res2.json()
        logger.info(f'{reqcodeRes}')
        parsed = urlparse(reqcodeRes['RedirectURL'])  
        reqCode = parse_qs(parsed.query)['code'][0]
        api_secret =config.FIN_APIKEY+ reqCode + config.FIN_SECRETKEY
        api_secret =  hashlib.sha256(api_secret.encode()).hexdigest()
        payload = {"api_key":config.FIN_APIKEY, "request_code":reqCode, "api_secret":api_secret}
        url3 = 'https://authapi.flattrade.in/trade/apitoken'  
        res3 = ses.post(url3, json=payload)
        logger.info(f'{res3.json()}')
        config.ACCESS_TOKEN = res3.json()['token']
        setConfig({'accesstoken':config.ACCESS_TOKEN })
        logger.info(f'ACCESS TOKEN  {config.ACCESS_TOKEN}')
        res = config.SHOONAY_OBJ.set_session(userid=config.FIN_USER, password=config.FIN_PWD, usertoken = config.ACCESS_TOKEN)
    
    
    ret = config.SHOONAY_OBJ.get_limits()
    logger.info(f'Limits  {ret}')



def Finvasialogin():
    
    config.SHOONAY_OBJ = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
    # storedToken = isTokenValid()
    # if storedToken is not None:
    #     config.ACCESS_TOKEN = storedToken
    #     res = config.SHOONAY_OBJ.set_session(userid=config.FIN_USER, password=config.FIN_PWD, usertoken = config.ACCESS_TOKEN)
    # else:
    #     res = config.SHOONAY_OBJ.login(userid= config.FIN_USER, password=config.FIN_PWD, twoFA=pyotp.TOTP( config.FIN_TOTP_TOKEN).now() , vendor_code=config.FIN_USER +'_U', api_secret=config.FIN_APIKEY, imei='asd5hsgyb6')
    #     config.ACCESS_TOKEN = res['susertoken']
    #     logger.info(f'ACCESS TOKEN  {config.ACCESS_TOKEN}')
    #     setConfig({'accesstoken':config.ACCESS_TOKEN })
    #     res = config.SHOONAY_OBJ.set_session(userid=config.FIN_USER, password=config.FIN_PWD, usertoken = config.ACCESS_TOKEN)
    
    config.SHOONAY_OBJ.set_session(userid=config.FIN_USER, password=config.FIN_PWD, usertoken = config.ACCESS_TOKEN)
    ret = config.SHOONAY_OBJ.get_limits()
    logger.info(f'Limits  {ret}')

from functools import lru_cache 
@lru_cache
def getMasterdf(url:str) -> pd.DataFrame:
    symbolDf = pd.read_csv(url,storage_options=  {"User-Agent": "pandas"})
    symbolDf['Expiry'] = pd.to_datetime(symbolDf['Expiry']).apply(lambda x: x.date())
    symbolDf['feedToken'] =  symbolDf.apply(lambda x: f'{x.Exchange}|{x.Token}', axis=1)
    return symbolDf

from copy import deepcopy
def initializer():
    try:
        FlatTradelogin()
        #Finvasialogin()
        url = f'https://api.shoonya.com/{config.EXCHANGE}_symbols.txt.zip'
        masterDf = getMasterdf(url).copy()
        config.MASTER_LIST = masterDf
        config.TOKEN_MAP = {}
        SYM_CONFIG =  deepcopy(config.SYM_CONFIG)
        for sym , symConfig in  SYM_CONFIG.items():
            if not symConfig['enable']:
                continue
            symbolDf = masterDf[(masterDf.Instrument == 'OPTIDX') & (masterDf.Symbol == sym) &  (masterDf.Expiry >= datetime.now(config.TIME_ZONE).date())]
            weekly_expiry = list(symbolDf['Expiry'].unique())
            weekly_expiry.sort()
            ocdf = symbolDf[(symbolDf.Expiry == weekly_expiry[0] )]
            config.TOKEN_MAP[sym] = ocdf
            spotSym = config.SYM_MAP[sym]  
            spotExch = 'NSE' if spotSym[1] =='NFO' else 'BSE'
            #spotltp = getLTPFin(spotSym[0],exch=spotExch)
            #feedDf = ocdf[(ocdf.StrikePrice > spotltp*0.95 ) & (ocdf.StrikePrice < spotltp*1.05 )]
            config.FEED_SYNTAX.extend(ocdf['feedToken'].tolist())
            config.FEED_SYNTAX.append(f'{spotExch}|{spotSym[0]}')
            config.SYM_CONFIG[sym].update({'spot_exch': spotExch,'spot_token': spotSym[0] ,'strikeGap':spotSym[3],'expiry':weekly_expiry[0]})
       
        logger.info(f'SYM_CONFIG: {config.SYM_CONFIG} ')
        logger.info(f'Symbol List \n {config.TOKEN_MAP} ')
        return True
    except :
        logger.exception(f'Error in intializer')
        return False



def getSymbolToken(strike_price, pe_ce,sym):
    tokenDf = config.TOKEN_MAP[sym] 
    return tokenDf[(tokenDf.StrikePrice ==strike_price) & (tokenDf.OptionType ==pe_ce) ].iloc[0].to_dict()
  
 
def getOrderSize(qty,freezeQty):
    size = math.floor(qty /freezeQty)
    lastOrderQty= int(qty % freezeQty)
    logger.info(f'Total no of order {size} LastOrderQty {lastOrderQty} ' )
    return size, lastOrderQty 

start =  TT()


def event_handler_feed_update(tick_data):
    #print('print ',tick_data)
    global start
    if 'lp' in tick_data and 'tk' in tick_data  and 'ft' in tick_data:
        timest = datetime.fromtimestamp(int(tick_data['ft']),tz=config.TIME_ZONE)
        config.FEED_JSON[tick_data['tk']] = {'ltp': float(tick_data['lp']) , 'tt': timest ,'Token':int(tick_data['tk'])}
    if TT() -start > 60 : 
        start =  TT()
        logger.info(f'\n {list(config.FEED_JSON.values())[:5] }')
    
def event_handler_order_update(tick_data):
    logger.info(f"---- Order update ----- : {tick_data}")
    if 'norenordno' in  tick_data:
        config.ORDER_STATUS[str(tick_data['norenordno'])] = tick_data
   

feed_opened = False
def open_callback():
    global feed_opened
    feed_opened = True
    config.SHOONAY_OBJ.subscribe(config.FEED_SYNTAX,2)
    
  

def close_callback(msg =None):
    logger.info(f"Connection Closed: {msg} {config.FEED_JSON}")


def error_callback(msg =None):
    logger.error(f"Error in connection : {msg}")

def connectFeed():
    
    config.SHOONAY_OBJ.start_websocket( order_update_callback=event_handler_order_update,
                        subscribe_callback=event_handler_feed_update, 
                        socket_open_callback=open_callback,socket_close_callback= close_callback, socket_error_callback = error_callback)

    while(feed_opened==False):
        pass
    #subscribe to multiple tokens
    sleep(2)
    #logger.info(f'Feed Subscribed \n {config.FEED_JSON}')

def addSymboltofeed(token, excahnge):
    config.SHOONAY_OBJ.subscribe(f'{excahnge}|{token}',2)
    logger.info(f'Subscribed {excahnge}|{token}')

def addSymbolListtofeed(feedList):
    config.SHOONAY_OBJ.subscribe(feedList)
    logger.info(f'Subscribed {feedList}')

def printConfig():
    configFile = inspect.getsource(config)  
    logger.info(configFile)

def getTimeCondition():
    startTime =  datetime.now(config.TIME_ZONE)
    closingTime = startTime.replace(hour=config.EXIT_TIME[0], minute=config.EXIT_TIME[1],second=0).time()
    return datetime.now(config.TIME_ZONE).time() >= time(9, 15, 0) and datetime.now(config.TIME_ZONE).time() < closingTime  and config.RUN_PROCESS


def OrderStatusPool():
    while getTimeCondition():
        try:
            orderRes = config.SHOONAY_OBJ.get_order_book()
            if orderRes is not None :
                for order in  orderRes:
                    config.ORDER_STATUS[order['norenordno']] = order

        except :
            logger.exception(f'Error in order Status Update')
        sleep(2)


def getOrderStatus( orderid):
    for _ in range(6):
        try:
            if orderid in  config.ORDER_STATUS:
                return config.ORDER_STATUS[str(orderid)]
            logger.info(f"Order {orderid} not found in order pool  : {config.ORDER_STATUS.keys()}")
            sleep(1)
        except :
            logger.exception(f'Error in fetching order Status')


def getLTPFin(token,exch=None):
    exch = config.EXCHANGE  if exch is None else exch
    qRes= config.SHOONAY_OBJ.get_quotes(exch,str(token))
    return float(qRes['lp'])


def getLtp(token,exch = None):
    token = str(token)
    exch = config.EXCHANGE  if exch is None else exch
    try:
        if (token in config.FEED_JSON) and (datetime.now(config.TIME_ZONE) - config.FEED_JSON[token]['tt']).total_seconds() < 120:
            return config.FEED_JSON[token]['ltp']
        raise Exception('Error in Feed')
    
    except:
        sleep(2)
        for i in range(1,5):
            try:
                res = config.SHOONAY_OBJ.get_quotes(exchange=exch, token=token)
                logger.error(f'Error in Live Feed {token}  {token in config.FEED_JSON} {res["lp"]}')
                ltp = float(res['lp'])
                return ltp
            except :
                logger.info(f'Ltp form api failed {token}')
                sleep(2)
        


def truncate(f):
    f = round(f / 0.05) * 0.05  # tick size 0.05
    n = 2
    s = '%.12f' % f
    i, p, d = s.partition('.')
    return float('.'.join([i, (d+'0'*n)[:n]]))



def printSendMsg(msg):
    logger.info(msg)




def telegram_bot_sendtext(bot_message):
    try:
        if config.BOT_TOKEN and config.BOT_CHAT_ID:
            bot_message =  str(bot_message).replace('&','')
            send_text = 'https://api.telegram.org/bot' + config.BOT_TOKEN + '/sendMessage?chat_id=' + config.BOT_CHAT_ID + '&parse_mode=HTML&text=' + bot_message
            res = requests.get(send_text)
            #s_logger.info(f'Telegram response : {res.json()}')
        
    except Exception as e:
        logger.exception(f'Error in sending Telegram msg {e}')


import threading
def printSendMsg(msg ):
    logger.info(msg)
    threading.Thread(target = telegram_bot_sendtext,args = [msg]).start()
   



def isAllOrderTraded(orderlist):
    try:
        if not orderlist : return False
        
        completeCount = 0
        for orderid in orderlist:
            orderDetail = getOrderStatus(orderid)
            if orderDetail['status'] == 'COMPLETE':
                completeCount =completeCount + 1
        return len(orderlist) == completeCount
        
    except Exception:
        logger.exception(f'Error in checking all orders')  



def getDelta(strike,optionType,price, spot,expDate):
    try:
        r = .1
        flag = 'p' if optionType == 'PE' else 'c'
        t = (datetime(expDate.year,expDate.month,expDate.day,15,30,0) - datetime.now())/timedelta(days= 1)/365
        IV = implied_volatility(price, spot, strike, t, r, flag)
        return delta(flag, spot, strike, t, r, IV)
    except Exception as e:
        return None

def getNearStrikePremium(premium :  float,optionType :str ,sym:str):
    liveOCdf = pd.DataFrame(config.FEED_JSON.values())
    symConfig  =  config.SYM_MAP[sym] 
    spotPrice  = getLTPFin(symConfig[0] ,symConfig[4])
    atmStrike  = round(spotPrice/symConfig[3])*symConfig[3]
    liveOCdf = liveOCdf.merge(config.TOKEN_MAP[sym],on ='Token')
    liveOCdf['diff'] = abs(liveOCdf['ltp']- premium)
    if optionType == 'CE':
        liveOCdf = liveOCdf[(liveOCdf['OptionType'] ==optionType) &  (liveOCdf.StrikePrice >= atmStrike)] 
    else:
        liveOCdf = liveOCdf[(liveOCdf['OptionType'] ==optionType) &  (liveOCdf.StrikePrice <= atmStrike)] 
    
    liveOCdf.sort_values(by = 'diff', inplace=True)
    logger.info(f"OC \n {liveOCdf[['ltp','TradingSymbol','StrikePrice','diff']]}")
    finalStrike = liveOCdf.iloc[0].to_dict()
    logger.info(f' Strike Near {premium} Selected {optionType} entry :  {finalStrike}')
    if abs((datetime.now(config.TIME_ZONE) - finalStrike['tt']).total_seconds())  > 120:
        logger.error(f'Option data delayed')
    return finalStrike





def getOptionChain(sym:str,expDate:datetime.date):

    liveOCdf = pd.DataFrame(config.FEED_JSON.values())
    symConfig  =  config.SYM_MAP[sym] 
    spotPrice  = getLTPFin(symConfig[0] ,symConfig[4])
    #atmStrike  = round(spotPrice/symConfig[3])*symConfig[3]
    liveOCdf = liveOCdf.merge(config.TOKEN_MAP[sym],on ='Token')

    for i in liveOCdf.index:
        try:
            row = liveOCdf.loc[i]
            deltag = getDelta(row['StrikePrice'],row['OptionType'],row['ltp'],spotPrice,expDate)
            liveOCdf.loc[i,'delta'] = deltag
        except Exception as e:
            logger.error(f'Error in delta computation {i}')
    logger.info(f"OC : \n {liveOCdf}")
    return  liveOCdf


def getNearDeltaStrike(ocDf,optionType,deltaValue):
    deltaValue = abs(deltaValue)
    optionDf = ocDf[ocDf.OptionType == optionType]
    optionDf['delta'] = abs(optionDf['delta'])
    optionDf['diff'] = abs(optionDf['delta']- deltaValue)
    optionDf.sort_values(by ='diff',inplace = True)
    strike = optionDf.iloc[0].to_dict()
    logger.info(f'strike Selected near {deltaValue} {optionType} is {strike}')
    return strike


if __name__ == '__main__':
    initializer()




