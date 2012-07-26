import os,sys, re
import time
from datetime import datetime, timedelta
# Gen3 common modules
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
import unixIPC
import asyncprocess
import signal

import google.protobuf

import postgresops
from mod_scheduler import scheduledb
import flowdb,filedb

DB_CHECK_INTERVAL = float(config.map['mod_flow']['db_check_interval'])
CACHE_CHECK_INTERVAL = float(config.map['mod_flow']['cache_check_interval'])

def check_db():
    # update status of files invalid->valid or fail
    postgresops.dbcur.execute("select files.id,tasks.id,tasks.status from flows.files,schedule.tasks where files.task_id=tasks.id and files.status=%s;",(filedb.INVALID,))
    if postgresops.dbcur.rowcount > 0:
        rows = postgresops.dbcur.fetchall()
        for fileid,taskid,status in rows:
            if ( status == scheduledb.DONE ):
                postgresops.dbcur.execute("update flows.files SET status=%s where id=%s",(filedb.VALID,fileid))
                postgresops.dbcon.commit()
            elif (status >= scheduledb.ERROR_CRASH ):
                postgresops.dbcur.execute("update flows.files SET status=%s where id=%s",(filedb.FAIL,fileid))
                postgresops.dbcon.commit()
    
    # update status of files fail->valid or fail->invalid
    postgresops.dbcur.execute("select files.id,tasks.id,tasks.status from flows.files,schedule.tasks where files.task_id=tasks.id and files.status=%s;",(filedb.FAIL,))
    rows = postgresops.dbcur.fetchall()
    for fileid,taskid,status in rows:
        if ( status == scheduledb.DONE ):
            postgresops.dbcur.execute("update flows.files SET status=%s where id=%s",(filedb.VALID,fileid))
            postgresops.dbcon.commit()
        elif (status >= scheduledb.WAITING_FOR_INPUT and status <= scheduledb.PAUSED ):
            postgresops.dbcur.execute("update flows.files SET status=%s where id=%s",(filedb.INVALID,fileid))
            postgresops.dbcon.commit()

    # update status of flows
    postgresops.dbcur.execute("select flowdef,curflows.source_name,curflows.source_id,curflows.time_from,curflows.time_to,every(files.status=%s) "+
                              "from flows.curflows,flows.files where curflows.status=%s and files.id=any(curflows.file_ids) "+
                              "group by flowdef,curflows.source_name,curflows.source_id,curflows.time_from,curflows.time_to",
                              (filedb.VALID,flowdb.RUNNING))
    
    if postgresops.dbcur.rowcount > 0:
        rows = postgresops.dbcur.fetchall()
        for flowdef,sname,sid,tfrom,tto,every in rows:
            if every:
                postgresops.dbcur.execute("update flows.curflows SET status=%s where flowdef=%s and source_name=%s and source_id=%s and time_from=%s and time_to=%s",
                                          (flowdb.DONE,flowdef,sname,sid,tfrom,tto))
            
        postgresops.dbcon.commit();

# connect to postgres
flowdb.connect()
if flowdb.connected():
    flowdb.initdb()
    filedb.initdb()
else:
    print "ERROR: Cannot connect to postgre database"
    sys.exit(1)


#timeouts
last_db_check = time.time()
last_cache_check = 0

while True:
    if ( not scheduledb.connected() ):
        scheduledb.connect()
    else:
        if ( time.time() - last_db_check > DB_CHECK_INTERVAL ):
            check_db()
            last_db_check = time.time()
        elif (time.time() - last_cache_check > CACHE_CHECK_INTERVAL):
            filedb.check_cache()
            last_cache_check = time.time()


            
    time.sleep(0.1)