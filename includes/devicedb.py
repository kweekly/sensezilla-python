# -*- coding: utf-8 -*-

import psycopg2, os, sys
import config
import utils
import postgresops
import random
from datetime import *

id_rgen = random.Random()
id_rgen.seed()

class Device:
    def __init__(self):
        self.ID = 0;
        self.IDstr = '';
        self.device_type = '';
        self.source_name = '';
        self.source_ids = []
    
        
class DeviceMeta:
    def __init__(self):
        self.ID = 0;
        self.parent = 0
        self.key = ''
        self.value = ''
        self.devices = []
        
def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected();

def initdb():
    res = postgresops.check_and_create_table(
         "devices.physical",
         (("id", "integer primary key"),
          ("idstr","varchar"),
          ("device_type","varchar"),
          ("source_name","varchar"),
          ("source_ids","varchar[]")
          ))
    
    res = postgresops.check_and_create_table(
         "devices.metadata",
         (("id", "integer primary key"),
          ("parent", "integer"),
          ("key","varchar"),
          ("value","varchar"),
          ("devices","integer[]")
          ))

def new_device():
    if connected():
        while True:
            newint = id_rgen.randint(10, 2**31-1)
            postgresops.dbcur.execute("SELECT id from devices.physical where id=%s limit 1",(newint,))
            if ( postgresops.dbcur.rowcount == None or postgresops.dbcur.rowcount <= 0):
                break
    else:
        newint = id_rgen.randint(10, 2**31-1)        
    
    dev = Device()
    dev.ID = newint
    return dev

def new_devicemeta():
    if connected():
        while True:
            newint = id_rgen.randint(10, 2**31-1)
            postgresops.dbcur.execute("SELECT id from devices.metadata where id=%s limit 1",(newint,))
            if ( postgresops.dbcur.rowcount == None or postgresops.dbcur.rowcount <= 0):
                break
    else:
        newint = id_rgen.randint(10, 2**31-1)        
    
    dev = DeviceMeta()
    dev.ID = newint
    return dev

def find_devices_under(meta):
    devidlist = find_device_ids_under(meta)
    postgresops.dbcur.execute("SELECT * from devices.physical where id=any(%s)",[devidlist,])
    retval = []
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(device_for_row(row))
        
    return retval

def find_device_ids_under(meta):
    devidlist = meta.devices
    metas = get_devicemetas(where="parent=%d"%meta.ID)
    for m in metas:
        devidlist += find_device_ids_under(m)
    return devidlist

def get_devices(where='',orderby='',limit=None):
    extra = ''
    if where != '':
        extra += ' WHERE '+where
    if orderby != '':
        extra += ' ORDER BY '+orderby
    if limit != None:
        extra += ' LIMIT %d'%limit
    
    retval = []
    
    postgresops.dbcur.execute("SELECT * from devices.physical"+extra+";")

        
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(device_for_row(row))
        
    return retval

def insert_device(dev):
    postgresops.dbcur.execute("INSERT INTO devices.physical"+ 
                "(id,idstr,device_type,source_name,source_ids) "+
                "VALUES ("+"%s,"*4+"%s)",row_for_device(dev))
    postgresops.dbcon.commit()
    
def insert_devicemeta(dev):
    postgresops.dbcur.execute("INSERT INTO devices.metadata"+ 
                "(id,parent,key,value,devices) "+
                "VALUES ("+"%s,"*4+"%s)",row_for_devicemeta(dev))
    postgresops.dbcon.commit()

def update_device(dev):
    postgresops.dbcur.execute("UPDATE devices.physical SET "+
                              "id=%s,idstr=%s,device_type=%s,source_name=%s,source_ids=%s where id=%s",row_for_device(dev)+(dev.ID,))
    postgresops.dbcon.commit()
    
def update_devicemeta(dev):
    postgresops.dbcur.execute("UPDATE devices.metadata SET "+
                              "id=%s,parent=%s,key=%s,value=%s,devices=%s where id=%s",row_for_devicemeta(dev)+(dev.ID,))
    postgresops.dbcon.commit()    
    
def delete_device(id):
    postgresops.dbcur.execute("DELETE from devices.physical where id=%s",[id,])
    postgresops.dbcon.commit()
    
def delete_devicemeta(id):
    postgresops.dbcur.execute("DELETE from devices.metadata where id=%s",[id,])
    postgresops.dbcon.commit()

def get_devicemetas(where='',orderby='',limit=None):
    extra = ''
    if where != '':
        extra += ' WHERE '+where
    if orderby != '':
        extra += ' ORDER BY '+orderby
    if limit != None:
        extra += ' LIMIT %d'%limit
    
    retval = []
    
    postgresops.dbcur.execute("SELECT * from devices.metadata"+extra+";")

    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(devicemeta_for_row(row))
        
    return retval

def row_for_device(dev):
    return ( dev.ID, dev.IDstr, dev.device_type, dev.source_name, dev.source_ids )
    
def device_for_row(row):
    dev = Device()
    ( dev.ID, dev.IDstr, dev.device_type, dev.source_name, dev.source_ids ) = row;
    return dev
    
def row_for_devicemeta(dev):
    return ( dev.ID, dev.parent, dev.key, dev.value, dev.devices );
    
def devicemeta_for_row(row):
    dev = DeviceMeta()
    ( dev.ID, dev.parent, dev.key, dev.value, dev.devices ) = row;
    return dev
        
if __name__ == '__main__':
    connect();
    initdb();
    
    