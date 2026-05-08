
import logging 
import sys 
from  datetime import datetime

from dateutil import  tz
IST=tz.gettz("Asia/Kolkata")
td = datetime.now(IST).date()

logging.Formatter.converter = lambda *args: datetime.now(tz=IST).timetuple()

logging.basicConfig(filename=f"flat_iron_{td}.log", format='%(asctime)s - %(levelname)s - %(message)s') 
  
logger=logging.getLogger() 
logger.setLevel(logging.INFO) 

stdout_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stdout_handler)

