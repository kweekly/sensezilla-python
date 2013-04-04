# -*- coding: utf-8 -*-
import os
import sys
import time
import psutil
import cgi

from jinja2 import * 
import httplib
import urllib

CODES = {
    "d00001" : ("P","0013A2004090FEA4", 0),
    "d00002" : ("P","0013A2004090FEA4", 1),
    "d00003" : ("P","0013A2004090FEA4", 2),
    "d00004" : ("P","0013A2004090FEA4", 3),
    "d00005" : ("C","00:12:6d:45:50:7f:77:4b_disaggregated", 3),
    "d00006" : ("C","00:12:6d:45:50:7f:77:4b_disaggregated", 4),
    "d00007" : ("R",{
                        "humidity":     "0013A2004090D79C",
                        "temperature":  "0013A2004090D79C",
                        "occupancy":    "0013A2004090D791",
                        "light":        "0013A2004090D79C"
                    })
 };

CODE_LINES = {}
con = None;
 
def get_smap_data(uuid):
    global con
    con.request("GET","/backend/api/prev/uuid/%s?starttime=%d&format=csv&tags=&"%(uuid,int(1000*time.time())));
    bmsresp = con.getresponse()
    datlines = bmsresp.read().splitlines()
    tm = 0;
    val = -1;
    for dl in datlines:
        if len(dl) > 0 and dl[0] != '#' and ',' in dl:
            tm,val = dl.split(',')
            break
            
    return float(val)
 
lookedstuffup = False
def lookupstuff():
    global lookedstuffup, CODE_LINES
    if lookedstuffup:
        return 
        
    import config
    import utils
    import devicedb
    import postgresops
    devicedb.connect()
    
    for code,dat in CODES.iteritems():
        if dat[0] == "P":
            dev = devicedb.get_devices(where="idstr='%s'"%dat[1],limit=1);
            if len(dev) != 1:
                CODE_LINES[code] = lambda:"ERROR: Can't find device";
                return;
            dev = dev[0]
            # get plug load names
            metas = devicedb.get_devicemetas(where="key like 'PLUGLOAD%d' and %d=any(devices)"%(dat[2],dev.ID),limit=1);
            if len(metas) != 1 or metas[0].parent == 0:
                loadstr = "UNKNOWN";
            else:
                meta = metas[0]
                if meta.parent == 1:
                    loads = [int(s) for s in meta.value.split(',')]
                else:
                    loads = [meta.parent]
                
                loadstr = ""
                for lid in loads:
                    loadnamemeta = devicedb.get_devicemetas(where="id=%d"%lid,limit=1)[0]
                    loadstr += loadnamemeta.value;
                    if lid != loads[-1]:
                        loadstr += " + "
                        
            # get uuid of power and current
            devdef = utils.read_device(dev.device_type)
            poweruuid = None
            currentuuid = None
            for feednameidx in range(len(devdef['feeds'])):
                feedname = devdef['feeds'][feednameidx]
                if 'power %d'%(dat[2]+1) in feedname.lower():
                    poweruuid = dev.source_ids[feednameidx]
                elif 'current %d'%(dat[2]+1) in feedname.lower():
                    currentuuid = dev.source_ids[feednameidx]
        
            CODE_LINES[code] = lambda loadstr=loadstr,poweruuid=poweruuid,currentuuid=currentuuid,dat=dat:  ("http://sensezilla.berkeley.edu:7500/showliveplot?title=%s&source=sensezilla&sourceid=%s"%(urllib.quote("Wattage of Device(s): %s (Instrument:%s Port:%d)"%(loadstr,dat[1],dat[2]+1)),poweruuid)+";Device(s): "+loadstr + "\n" +
                                        "Wattage: %.2f W"%(get_smap_data(poweruuid)) + "\n" + 
                                        "Amperage: %.2f A"%(get_smap_data(currentuuid)));
                
        elif dat[0] == "R":
            devs = {}
            for t,v in dat[1].iteritems():
                dev = devicedb.get_devices(where="idstr='%s'"%v,limit=1);
                if len(dev) != 1:
                    CODE_LINES[code] = lambda:"ERROR: Can't find device %s"%v;
                    return;
                devs[t] = dev[0]
            
            occuuid   = devs['occupancy'].source_ids[2];
            humiduuid = devs['humidity'].source_ids[0];
            tempuuid  = devs['temperature'].source_ids[1];
            lightuuid = devs['light'].source_ids[3];
            
            CODE_LINES[code] = lambda occuuid=occuuid,humiduuid=humiduuid,tempuuid=tempuuid,lightuuid=lightuuid:  ("http://sensezilla.berkeley.edu:7500/showliveplot?title=%s&source=sensezilla&sourceid=%s"%(urllib.quote("Occupancy of room"),occuuid)+";"+
                                        "Occupancy: %.1f %%"%(get_smap_data(occuuid)) + "\n" +
                                        "Humidity: %.1f %%RH"%(get_smap_data(humiduuid)) + "\n" + 
                                        "Temperature: %.1f C"%(get_smap_data(tempuuid))  + "\n" +
                                        "Light Level: %.1f ulux"%(1.0e6*get_smap_data(lightuuid)));
                
        else:
            CODE_LINES[code] = lambda:"NOT IMPLEMENTED"
    
    lookedstuffup = True


def do_qrdata(environ, start_response):
    global con
    lookupstuff()

    start_response('200 OK',[('Content-Type','text/plain')])
    con = httplib.HTTPConnection("sensezilla.berkeley.edu");
    resp = []
    for code in CODES.keys():
        resp.append("%s;%s\n"%(code,CODE_LINES[code]().replace('\n',';')));
        
    con.close();
    return resp;