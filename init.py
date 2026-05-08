import threading
from datetime import datetime ,timedelta
from time import sleep, time as TT
import warnings
from copy import deepcopy
import Utility
from Logger import logger
import pandas_ta as ta
import config
from finOrder import place_order

warnings.filterwarnings('ignore')
dict_lock = threading.Lock()

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

def getTimeCondition():
    startTime =  datetime.now(config.TIME_ZONE)
    closingTime = startTime.replace(hour=config.EXIT_TIME[0], minute=config.EXIT_TIME[1],second=0).time()
    return datetime.now(config.TIME_ZONE).time() < closingTime  and config.RUN_PROCESS

def isAllOrderTraded(orderlist):
    try:
        if not orderlist : return False
        
        completeCount = 0
        for orderid in orderlist:
            orderDetail = Utility.getOrderStatus(orderid)
            if orderDetail['status'] == 'COMPLETE':
                completeCount =completeCount + 1
        return len(orderlist) == completeCount
        
    except Exception:
        logger.exception(f'Error in checking all orders')


def calculateRollStd(sym):
    shoonyaOrder = place_order()
    symConfig  =  config.SYM_MAP[sym]  
    optdf  = config.TOKEN_MAP[sym] 
    data =  shoonyaOrder.getCandleData(token = symConfig[0],exch = symConfig[4],tsym= sym)
    data['atm'] = round(data['intc']/symConfig[3])*symConfig[3]
    df = data[['ssboe','atm']]
    df.columns = ['time','atm']
    df[['open', 'high', 'low', 'close', 'volume']] = None
    strikeList = df['atm'].unique().tolist()

    ceStrikeMap = {}
    peStrikeMap = {}
    strikedf = optdf[optdf.StrikePrice.isin(strikeList)]
    for i in strikedf.index:
        tokeSymInfo = strikedf.loc[i]
        token = int(tokeSymInfo['Token'])
        optType = tokeSymInfo['OptionType']
        strikePrice = float(tokeSymInfo['StrikePrice'])
        print(token, optType, strikePrice)
        sdf = shoonyaOrder.getCandleData(token = str(token),exch = tokeSymInfo['Exchange'],tsym= tokeSymInfo['TradingSymbol'])
        if optType == 'CE':
            ceStrikeMap[strikePrice] = sdf
        else:
            peStrikeMap[strikePrice] = sdf 


    for idx, row in df.iterrows():
        strike = row['atm']
        time_val = row['time']
        
        if strike in ceStrikeMap and   strike in peStrikeMap:
            df2 = ceStrikeMap[strike]
            df3 = peStrikeMap[strike]
            #display(df2.head(1))
            matchCE = df2[df2['ssboe'] == time_val]
            matchPE = df3[df3['ssboe'] == time_val]
            if not matchCE.empty and not matchPE.empty:
                df.at[idx, 'open'] = matchCE.iloc[0]['into'] +  matchPE.iloc[0]['into']
                df.at[idx, 'high'] = matchCE.iloc[0]['inth'] +  matchPE.iloc[0]['inth']
                df.at[idx, 'low'] = matchCE.iloc[0]['intl'] +  matchPE.iloc[0]['intl']
                df.at[idx, 'close'] = matchCE.iloc[0]['intc'] +  matchPE.iloc[0]['intc']
                df.at[idx, 'volume'] = matchCE.iloc[0]['intv'] +  matchPE.iloc[0]['intv']
    

    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    df.set_index('time',inplace = True)
    df['vwap'] = ta.vwap(df.high, df.low, df.close, df.volume)
    df.reset_index('time',inplace = True)
    if len(df) > config.EMA_LENGTH:
        df['ema'] = ta.ema(df.close,length = config.EMA_LENGTH)
    else:
        df['ema'] = None
    logger.info(f'Roll Std for {sym}  \n {df.tail(3)}')
    return df



def isAnyOrderTraded(orderlist):
    try:
        if not orderlist : return False
        for orderid in orderlist:
            orderDetail = Utility.getOrderStatus(orderid)
            if orderDetail['status'] == 'COMPLETE':
                return True
        
    except Exception:
        logger.exception(f'Error in checking all orders')


def closePosition(symConfig : dict):
    shoonyaOrder = place_order()
    for opt , optConfig in  symConfig.items():
        try:
            tsym = optConfig['sellSym']
            btsym = optConfig['buySym']
            fillQty = optConfig['fillqty']
            logger.info(f'Closing {tsym} ')    
            sellExitPrice = shoonyaOrder.exitPositionBySymbol(tsym,fillQty,'S')
            logger.info(f'Closing {btsym} ')    
            buyExitPrice = shoonyaOrder.exitPositionBySymbol(btsym,fillQty,'B')
        except Exception:
            logger.exception(f'Error in checking all orders')       

def placeInitialOrder(sym , symConfig):

    shoonyaOrder = place_order()
    spotConfig  =    config.SYM_MAP[sym] 
    spotPrice   = Utility.getLTPFin(spotConfig[0] ,symConfig['spot_exch'])
    atmStrike = round(spotPrice/spotConfig[3])*spotConfig[3]
    logger.info(f'ATM strike {atmStrike}  ')

    ocdf = Utility.getOptionChain(sym,symConfig['expiry'])
    ceSymInfo = Utility.getNearDeltaStrike(ocdf,optionType='CE',deltaValue =symConfig['sellDelta'])
    peSymInfo = Utility.getNearDeltaStrike(ocdf,optionType='PE',deltaValue =symConfig['sellDelta'])

    ceHedgeSymInfo = Utility.getSymbolToken(ceSymInfo['StrikePrice'] + symConfig['buyStrike'], 'CE',sym)
    peHedgeSymInfo = Utility.getSymbolToken(peSymInfo['StrikePrice'] - symConfig['buyStrike'], 'PE',sym)
    logger.info(f'{sym} CE Buy sym {ceHedgeSymInfo}  ')
    logger.info(f'{sym} PE Buy sym {peHedgeSymInfo}  ')
 

    try:
        
        qty = symConfig['qty']*int(ceSymInfo['LotSize'])
        #buyLimitPrice = shoonyaOrder.getLimitPrice(symbolInfo['Token'],symbolInfo['Exchange'],'B')
        ceEntryOrderList = shoonyaOrder.placeMultipleOrder(ceHedgeSymInfo["TradingSymbol"],qty,limitPrice=0, transType = 'B')
        peEntryOrderList = shoonyaOrder.placeMultipleOrder(peHedgeSymInfo["TradingSymbol"],qty,limitPrice=0, transType = 'B')

        for _ in range(10):
            isAllBuyTraded = isAllOrderTraded(ceEntryOrderList + peEntryOrderList)
            if isAllBuyTraded  or config.IS_TEST:
                Utility.printSendMsg(f'Hedge order traded completly')
                ceSellOrderList = shoonyaOrder.placeMultipleOrder(ceSymInfo["TradingSymbol"],qty,limitPrice=0, transType = 'S')
                peSellOrderList = shoonyaOrder.placeMultipleOrder(peSymInfo["TradingSymbol"],qty,limitPrice=0, transType = 'S')
                
                for __ in range(10):
                    isAllSellTraded = isAllOrderTraded(ceSellOrderList + peSellOrderList)
                    if isAllSellTraded  or config.IS_TEST:
                        orderDf = shoonyaOrder.getOrderbook()   
                        Utility.printSendMsg(f'Sell order traded completly')   
                        config.POSITION_JSON[sym] = {} 
                        for optionType,buyOrderid, sellOrderList in  [('CE',ceEntryOrderList[0],ceSellOrderList),  ('PE',peEntryOrderList[0], peSellOrderList)]:
                            try:
                                buyOrderInfo = orderDf[orderDf.norenordno == str(buyOrderid)].iloc[0].to_dict()
                                buySym = buyOrderInfo['tsym']
                                buytradedPrice = float(buyOrderInfo['avgprc'])    if not config.IS_TEST else   Utility.getLTPFin(buyOrderInfo['token'] ,buyOrderInfo['exch'])
                                slOrderList = []
                                for sellOrder in sellOrderList:  
                                    sellOrderInfo = orderDf[orderDf.norenordno == str(sellOrder)].iloc[0].to_dict()
                                    sellSym = sellOrderInfo['tsym']
                                    sellTradedPrice = float(sellOrderInfo['avgprc'])    if not config.IS_TEST else   Utility.getLTPFin(sellOrderInfo['token'] ,sellOrderInfo['exch'])
                                    Utility.printSendMsg(f'{sellSym} {qty} traded {sellTradedPrice} \n {buySym} {qty} traded {buytradedPrice} ')
                               
                                config.POSITION_JSON[sym][optionType] = {**symConfig, 'fillqty':qty, 'exch': sellOrderInfo['exch'] , 'sellSym':sellSym, 'buySym':buySym,
                                    'lot': ceSymInfo['LotSize'] ,'sellTradedPrice':sellTradedPrice, 'buytradedPrice':buytradedPrice, 
                                    'sellToken': sellOrderInfo['token'] ,'buyToken':buyOrderInfo["token"] , 'realizeGain':0 }
                                
                                logger.info(f'After entry  {optionType}  {config.POSITION_JSON}')
                                
                            except:
                                Utility.printSendMsg(f'{optionType} Error in order placement')
                                logger.exception(f'{optionType} Error in order placement ')
                                break
                        return
                    sleep(2)
                
            sleep(2)
            # else:
            #     sleep(2)
            #     orderDf = shoonyaOrder.getOrderbook()       
            #     for sellOrder in  entryOrderList:
            #         #sellOrderInfo = Utility.getOrderStatus(sellOrder)
            #         sellOrderInfo = orderDf[orderDf.norenordno == str(sellOrder)].iloc[0].to_dict()
            #         sellLimitPrice = shoonyaOrder.getLimitPrice(sellOrderInfo['token'],sellOrderInfo['exch'],entryOrderSide)
            #         logger.info(f'Modify {sellOrder} to limitprice   {sellLimitPrice}')
            #         shoonyaOrder.modify_limit(sellOrderInfo,sellLimitPrice)
        
    except :
        logger.exception(f'Error in Entry order placement ')
    Utility.printSendMsg(f'Entry failed')
    logger.info(f'{config.POSITION_JSON}')



"""
{'enable':True,'qty':1,'sellPremium':20,'ltpSum':10,'adjustmentPrcnt':50,'buyStrike':1000, 'mtmSLprcnt':2, 'fillqty':qty, 'exch': sellOrderInfo['exch'] ,  'spot_exch': ,
'sellSym':sellSym, 'buySym':buySym,
    'lot': ceSymInfo['LotSize'] ,'sellTradedPrice':sellTradedPrice, 'buytradedPrice':buytradedPrice,
    'sellToken': sellOrderInfo['token'] ,'buyToken':buyOrderInfo["token"] }

"""
def checkAdjustment():
    logger.info(f'----------- Adjustemnt func Started  ----------')
    start = TT()   
    pnlGap = TT()
    while getTimeCondition():
        try:
            with  dict_lock:
                POSITION_JSON = deepcopy(config.POSITION_JSON)
                if TT() - start > 60 :
                    start = TT()
                    logger.info(f'POSITION  CONFIG : {config.POSITION_JSON} ')

                for sym , entryConfig in  POSITION_JSON.items():
                    if not entryConfig:
                        continue
                    PNL = 0
                    symConfig = config.SYM_CONFIG[sym]
                    mtmSL = -symConfig['margin']*symConfig['mtmSLprcnt']/100
                    pnlMap = {'CE':0, 'PE':0}
                    try:
                        for opt , optConfig in entryConfig.items():
                            tsym = optConfig['sellSym']
                            fillQty = optConfig['fillqty']
                            sellLtp = Utility.getLtp(optConfig['sellToken'], optConfig['exch'])
                            buyLtp = Utility.getLtp(optConfig['buyToken'], optConfig['exch'])
                            sellTradedPrice = optConfig['sellTradedPrice']
                            buytradedPrice = optConfig['buytradedPrice']
                            optPnl = (buyLtp - buytradedPrice)*fillQty + (sellTradedPrice- sellLtp)*fillQty
                            pnlMap[opt] = optPnl
                            PNL += optPnl
                    except Exception:
                        logger.exception(f'Error in adjustment check for {sym} ')
                    
                    if TT() - pnlGap > 60 :
                        pnlGap = TT()
                        logger.info(f'{sym} Open Position PNL => CE:{pnlMap["CE"]} + PE: {pnlMap["PE"]} = {PNL} ')
                

                    if PNL < mtmSL:
                        Utility.printSendMsg(f'{sym} {pnlMap["CE"]} + {pnlMap["PE"]} = {PNL}  is less than MTM SL {mtmSL} ')
                        closePosition(config.POSITION_JSON[sym])
                        del config.POSITION_JSON[sym]

               
        except  Exception:
            logger.exception(f'Error in adjustemnt check ')
        sleep(config.SCAN_INTERVAL)
    logger.info(f'----------- Adjustemnt func Ended  ----------')



def scanEntryExit():
    SYM_CONFIG =  deepcopy(config.SYM_CONFIG)
    emaExitTime = datetime.now(config.TIME_ZONE).replace(hour=config.EMA_EXIT_TIME[0], minute=config.EMA_EXIT_TIME[1],second=config.EMA_EXIT_TIME[2])
    for sym , symConfig in  SYM_CONFIG.items():
            try:
                if not symConfig['enable']:
                    continue
                candledf = calculateRollStd(sym)
                recentCandle = candledf.iloc[-1]
                prvsCandle = candledf.iloc[-2]
                isEntry =  False
                isExit =  False

                if  recentCandle['close'] < recentCandle['vwap']   and ( not config.IS_ENTRY_ON_CROSS  or  (config.IS_ENTRY_ON_CROSS and  prvsCandle['close'] > prvsCandle['vwap']) ) :
                    isEntry = True

                if  recentCandle['close'] > recentCandle['vwap'] and abs(recentCandle['close'] - recentCandle['vwap']) > config.EXIT_BUFFER:
                    Utility.printSendMsg(f"Vwap Exit condition met for {sym}  {recentCandle['close']} > {recentCandle['vwap']} ")
                    isExit = True
                
                elif datetime.now(config.TIME_ZONE) > emaExitTime and recentCandle['ema'] and recentCandle['close'] > recentCandle['ema'] :
                    Utility.printSendMsg(f"Ema Exit condition met for {sym}  {recentCandle['close']} > {recentCandle['ema']} ")
                    isExit = True

                if sym in config.POSITION_JSON  and isExit:
                    closePosition(config.POSITION_JSON[sym])
                    config.POSITION_JSON.pop(sym, None)
                    logger.info(f'Reset entry config {config.POSITION_JSON} ')

                elif isEntry and sym not in config.POSITION_JSON:
                    logger.info(f'Entry condition met for {sym} ')
                    placeInitialOrder(sym , symConfig)

            except:
                logger.exception(f'Error {sym} intial Order placement')


def checkEntryConditions():
    #interval = Utility.getSyncTime()
    #sleep(interval)
    while  getTimeCondition():
        with dict_lock:
            scanEntryExit()
        interval = getSyncTime()
        logger.info(f' Next Scan After {interval} sec')
        sleep(interval)



def getSyncTime():
    tf = config.TRADE_TIMEFRAME
    currenttime =datetime.now(config.TIME_ZONE)
    minutes = (currenttime - timedelta(minutes=15)).minute
    remaintime = minutes%tf  
    interval = (tf -remaintime)*60 - currenttime.second
    return interval

def start():
    Utility.printConfig()
    startTime = datetime.now(config.TIME_ZONE)
    closingTime = startTime.replace(hour=config.ENTRY_TIME[0], minute=config.ENTRY_TIME[1],second=config.ENTRY_TIME[2]) 
    interval =max(0, (closingTime - startTime).total_seconds())
    Utility.printSendMsg(f'Wait  {interval} sec')
    sleep(interval)
    if Utility.initializer():
        Utility.connectFeed()
        threading.Thread(target=Utility.OrderStatusPool,daemon=True).start()
        threading.Thread(target=checkAdjustment,daemon=True).start()
        checkEntryConditions()
    else:
        Utility.printSendMsg(f"intailization Failed Try Again")


if __name__ == '__main__':
    start()
