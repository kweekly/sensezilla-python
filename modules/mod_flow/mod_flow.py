import os,sys, re
import time
from datetime import datetime, timedelta
# Gen3 common modules
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import util
import unixIPC
import asyncprocess
import signal

import google.protobuf

from mod_scheduler import scheduledb
import flowdb

DB_CHECK_INTERVAL = float(config.map['mod_flow']['db_check_interval'])

def check_db():
    pass



# connect to postgres
flowdb.connect()
if flowdb.connected():
    flowdb.initdb()
else:
    print "ERROR: Cannot connect to postgre database"
    sys.exit(1)


#timeouts
last_db_check = time.time()

while True:
    if ( not scheduledb.connected() ):
        scheduledb.connect()
    else:
        if ( time.time() - last_db_check > DB_CHECK_INTERVAL ):
            check_db()
            last_db_check = time.time()
            
    time.sleep(0.1)