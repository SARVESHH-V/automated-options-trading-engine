
import pandas as pd
import math
import  config
from Logger import  logger
import Utility
import time
from time import sleep
from datetime import datetime as dt, timedelta
from NorenApi import NorenApi

class place_order:
    def __init__(self):
        self.shoonya :NorenApi = config.SHOONAY_OBJ 
    
    def placeorder(self, symbol, buySell,qty,orderType,exchange, price=0,trigger_price=0 ):
        #return None
        res= self.shoonya.place_order(buy_or_sell=buySell, product_type=config.ORDER_TYPE,
                        exchange=exchange, tradingsymbol=symbol.strip(), 
                        quantity=qty, discloseqty=0,price_type=orderType, price=self.truncate(price), trigger_price=self.truncate(trigger_price),
                        retention='DAY', remarks=config.ORDER_TAG)
        logger.info(f'Order Res {res} {symbol} {qty} {buySell} {orderType} LimitPrice {price} triggerPrice {trigger_price} ') 
        config.ENTER_SYMBOL.append(symbol.strip())
        if res and res['stat'] == 'Ok' and 'norenordno' in res:
            Utility.printSendMsg(f'{buySell} Order Placed For {symbol} {qty}  {orderType} ')
            return res['norenordno']
        else:
            Utility.printSendMsg(f"Error in Order Placement {res}")


    
    def getCandleData(self, exch,token,tsym=None):
        try:
            for i in range(2):
                lastBusDay = dt.now(config.TIME_ZONE)
                lastBusDay = lastBusDay.replace(hour=9, minute=15, second=0, microsecond=0)
                ret = self.shoonya.get_time_price_series(exchange=exch, token=str(token), starttime=lastBusDay.timestamp(),endtime=dt.now(config.TIME_ZONE).timestamp(), interval=config.TRADE_TIMEFRAME)
                data= pd.DataFrame(ret)
                if len(data) == 0  or ret is None:
                    logger.info(f"{token}:{tsym} Candle data None {ret}. ")
                    sleep(i)
                    continue
                    
                data[['ssboe', 'into','inth','intl','intc','v']] = data[['ssboe', 'into','inth','intl','intc','v']].apply(pd.to_numeric)
                data['ssboe'] = data['ssboe'].apply(pd.Timestamp, unit='s', tzinfo=config.TIME_ZONE)
                data.sort_values(by ='ssboe',inplace =True)

                recentTime = dt.now(config.TIME_ZONE)
                startTime = recentTime.replace(hour=9, minute=15,second=0)
                minFromStart = math.floor((dt.now(config.TIME_ZONE) -startTime).seconds/60)
                timeFrame = config.TRADE_TIMEFRAME
                lastTf = int(minFromStart/timeFrame)*timeFrame - timeFrame 
                lastTimeStamp = startTime + timedelta(minutes=lastTf)
                data = data[(data.ssboe <= lastTimeStamp)]
                data.reset_index(drop =True,inplace=True)
                logger.info(f"{token}:{tsym} Candle data \n {data.tail(2)}")
                return data
        except :
            logger.exception(f'Error in {token}')
      
    def getPositionBook(self) -> pd.DataFrame:
        try:
            for _ in range(10):
                ret = self.shoonya.get_positions()
                if ret is not None :
                    return pd.DataFrame(ret)
                logger.error(f"Error in Position  api {ret} ")
                time.sleep(1)
        except Exception as e:
            logger.exception(f'Position book  Failed') 


    def truncate(self, f):
        ticksize = 0.05*100
        remainder = int(str(f*100.0).split('.')[0][-2:])
        pp = int((int(remainder/ticksize)*ticksize))
        if len(str(pp))  == 1:
            return float(str(int(f)) + '.0' + str(pp))
        else:
            return float(str(int(f)) + '.' + str(pp))
           
    
    def getOrderbook(self,orderTag = None):
        for i in range(1,4):
            try:
                ret = self.shoonya.get_order_book()
                orderDf = pd.DataFrame(ret)
                if orderTag is None or 'remarks' not in orderDf:
                    return orderDf
                else:
                    return orderDf[orderDf.remarks ==orderTag]

            except Exception as e:
                logger.exception(f'Orderbook  Failed {orderTag} ') 
                time.sleep(i)

    def getExecutedPrice(self,orderid,noWait = False):
        executedPrice = 0
        for i in range(1,5):
            try:
                orderDf = self.getOrderbook()
                orderInfo = orderDf[orderDf.norenordno == str(orderid)].iloc[0].to_dict()
                if 'avgprc' in orderInfo  and   float(orderInfo['avgprc']) > 0 and orderInfo['status'] == 'COMPLETE':
                    return float(orderInfo['avgprc'])
                if noWait:
                    break
            except Exception as e:
                logger.error(f'Get Entry Price Failed {orderid}') 
            time.sleep(5)
        return executedPrice

   

    def isALLOrderPlaced(self,orderList):
        try:
            orderDf = self.getOrderbook()
            orderDf = orderDf[orderDf.norenordno.isin(orderList)]
            for i in orderDf.index:
                order= orderDf.loc[i]
                if order['status'] == 'REJECTED':
                    logger.info(f'Order Rejected {order.to_dict()}') 
                    return False
        except:
            logger.error(f'Order Status Failed {orderList}') 
        return True

    
    
    def exitPositionBySymbol(self,tsym, qty = 0, side =None):
        posDf = self.getPositionBook()
        logger.info(f"{tsym} Position book \n  {posDf.to_json(orient='records')}")
        try:
            if posDf is not None and len(posDf) > 0 :
                openPos = posDf[(posDf.netqty != '0') & (posDf.prd == config.ORDER_TYPE) & (posDf.exch == config.EXCHANGE) & (posDf.tsym == tsym) ]
                for i in openPos.index: 
                    try:
                        openPosInfo = openPos.loc[i]
                        netQty = int(openPosInfo['netqty'])
                        if side is not None and  (side == 'S' and netQty > 0) : 
                            continue
                        if qty == 0 : qty = netQty
                        
                        buySell = 'B' if netQty < 0  else 'S'
                        #self.placeorder(openPosInfo['tsym'], buySell,abs(netQty),'MKT',openPosInfo['exch'] )
                        #limitPrice = self.getLimitPrice(openPosInfo['token'],openPosInfo['exch'],buySell)
                        orderlist = self.placeMultipleOrder(openPosInfo['tsym'],min(abs(netQty) , abs(qty)),limitPrice=0, transType = buySell)
                        time.sleep(1)
                        for j in range(10):  
                            if Utility.isAllOrderTraded(orderlist):
                                exitOrderInfo = Utility.getOrderStatus(orderlist[0])
                                exitPrice = float(exitOrderInfo['avgprc']) 
                                Utility.printSendMsg(f" Position Closed  {openPosInfo['tsym']} at {exitPrice} ") 
                                return exitPrice
                           
                            # for sellOrder in  orderlist:
                            #     sellOrderInfo = Utility.getOrderStatus(sellOrder)
                            #     if sellOrderInfo['status'] == 'COMPLETE':
                            #         continue
                            #     sellLimitPrice = self.getLimitPrice(openPosInfo['token'],openPosInfo['exch'],sellOrderInfo['trantype'])
                            #     logger.info(f'Modify {sellOrder} to limitprice   {sellLimitPrice}')
                            #     self.modify_limit(sellOrderInfo,sellLimitPrice)
                            time.sleep(j)
                        else:
                            Utility.printSendMsg(f"ERROR: {side} {openPosInfo['tsym']} Position Not  Closed ") 
                    except :
                        logger.exception(f'Error in positon close {tsym}') 
                        Utility.printSendMsg(f" Failed to close position  {tsym}") 
        except Exception as e:
            logger.exception(f'Error in positon close {posDf}  ') 
            Utility.printSendMsg(f"ERROR: Failed to close position  {tsym}")

    def cancelAllOrder(self):
        orderdf = self.getOrderbook(config.ORDER_TAG)
        for i in orderdf.index:
            orderInfo = orderdf.loc[i]
            if orderInfo['status'] in ['OPEN','TRIGGER_PENDING']:
                self.cancellOrderByid(orderInfo['norenordno'])

    def cancellOrderByid(self,orderno):
        try:
            ret = self.shoonya.cancel_order(orderno=orderno)
            logger.info(f'Cancellation Response {ret} ') 
            Utility.printSendMsg(f'{orderno} Order cancelled ')
        except Exception as e:
            logger.exception(f'Error in order cancellation close {orderno} {e} ') 
    
    
    def get_security_info(self, token,exchange='NFO',):
        return self.shoonya.get_security_info(exchange=exchange, token=str(token))

   
    
    def placeMultipleOrder(self,tradingsymbol,qty,limitPrice, transType = 'S'):
        orderList = []
        try:
            masterdf = config.MASTER_LIST
            sym = masterdf[masterdf.TradingSymbol == tradingsymbol].iloc[0]['Symbol']
            freezeQty =config.SYM_MAP[sym][2]
            size, lastOrderQty = Utility.getOrderSize(qty ,freezeQty)
            orderType = 'MKT' if limitPrice == 0 else 'LMT'
            if lastOrderQty > 0:
                orderid1 = self.placeorder(tradingsymbol, transType,lastOrderQty,orderType,config.EXCHANGE, price=limitPrice)
                if orderid1 is not None : orderList.append(orderid1)
                    
            for i in range(0,size):
                try:
                    orderid = self.placeorder(tradingsymbol, transType,freezeQty,orderType,config.EXCHANGE, price=limitPrice)
                    if orderid is not None : orderList.append(orderid)
                except Exception:
                    logger.exception(f'Error in placing multiple order {tradingsymbol} ')
        except  Exception:
            logger.exception(f'Error in placing order {tradingsymbol} {qty}')
        
        return  orderList

    
    def getLimitPrice(self,token, exch,transType):
        qRes= self.shoonya.get_quotes(exch,str(token))
        logger.info(f'{token} {transType} Quotes: {qRes} ')
        if transType == 'B' and 'sp5' in qRes :
            return float(qRes['sp5'])
        elif transType == 'S' and 'bp5' in qRes :
            return float(qRes['bp5'])
        return float(qRes['lp'])