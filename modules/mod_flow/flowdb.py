import psycopg2, os, sys
import config
import utils
import postgresops
import random
from datetime import *

(
STOPPED,
RUNNING,
DONE,
ERROR
) = range(4)



class Flow:
    def __init__(self):
        from flow_processor import FlowDef
        self.flowdef = FlowDef()
        self.time_from = datetime.now();
        self.time_to = datetime.now();
        self.source_name = ''
        self.source_id = ''
        self.task_ids = []
        self.status = STOPPED
        

def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected()

def initdb():
    res = postgresops.check_and_create_table(
         "flows.curflows",
         (("flowdef", "varchar"),
          ("time_from","timestamp"),
          ("time_to","timestamp"),
          ("source_name","varchar"),
          ("source_id","varchar"),
          ("task_ids","integer[]"),
          ("status","integer")
          ))
    
def add_flow(flow):
    postgresops.dbcur.execute("INSERT INTO flows.curflows"+ 
                "(flowdef,time_from,time_to,source_name,source_id,task_ids,status) "+
                "VALUES ("+"%s,"*6+"%s)",row_for_flow(flow))
    postgresops.dbcon.commit()
    
def update_entire_flow(flow):
    postgresops.dbcur.execute("UPDATE flows.curflows SET"+
                              "flowdef=%s,time_from=%s,time_to=%s,source_name=%s,source_id=%s,task_ids=%s,status=%s",row_for_task(task))
    postgresops.dbcon.commit()
    
def update_flow(flow,field_name,field_val):
    postgresops.check_evil(field_name);
    postgresops.dbcur.execute("UPDATE flows.curflows SET "+field_name+"=%s where time_from=%s and time_to=%s and source_name=%s and source_id=%s",
                              (field_val,flow.time_from,flow.time_to,flow.source_name,flow.source_id))
    postgresops.dbcon.commit()
    
def update_flow_mult(flowtask,fields):
    for field,val in fields:
        postgresops.check_evil(field);
        
    postgresops.dbcur.execute("UPDATE flows.curflows SET "+",".join([field+"=%s" for field,val in fields])+" where time_from=%s and time_to=%s and source_name=%s and source_id=%s",
                              [val for field,val in fields]+[flow.time_from,flow.time_to,flow.source_name,flow.source_id])
    postgresops.dbcon.commit()
    

def get_flows(where='',orderby='',limit=None):
    extra = ''
    if where != '':
        extra += ' WHERE '+where
    if orderby != '':
        extra += ' ORDER BY '+orderby
    if limit != None:
        extra += ' LIMIT %d'%limit
    
    retval = []
    
    postgresops.dbcur.execute("SELECT * from flows.curflows"+extra+";")

        
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(flow_for_row(row))
        
    return retval

def count(where=''):
    if where != '':
        postgresops.dbcur.execute("SELECT count(*) from flows.curflows WHERE "+where+";")
    else:
        postgresops.dbcur.execute("SELECT count(*) from flows.curflows;")
        
    return postgresops.dbcur.fetchone()[0];

def row_for_flow(flow):
    return ( flow.flowdef.name, flow.time_from, flow.time_to, flow.source_name, flow.source_id, flow.task_ids, flow.status )
    
def flow_for_row(row):
    from flow_processor import read_flow_file
    flow = Flow()
    ( fname, flow.time_from, flow.time_to, flow.source_name, flow.source_id, flow.task_ids, flow.status ) = row;
    flow.flowdef = read_flow_file(fname);
    return flow
    

    