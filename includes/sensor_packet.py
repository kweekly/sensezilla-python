# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import time, os, sys, struct
import config, utils

MT_TIMESYNC                = 0x00
MT_SENSOR_DATA             = 0x01
MT_CONFIGURE_SENSOR        = 0x02
MT_ACTUATE                 = 0x03
 
dev_BT_cache = {}
 
def populate_BT_cache():
    global dev_BT_cache
    dev_BT_cache = {}
    print "Scanning for MT values"
    devs = utils.list_devicedefs()
    for devf in devs:
        dev = utils.read_device(devf)
        
        if ( 'SPF_BT' in dev ):
            btstr = dev['SPF_BT']
            if not 'SPF_field_bitmask' in dev:
                print "Warning: SPF_field_bitmask not present for devdef "+devf
                continue;
            if not 'SPF_field_types' in dev:
                print "Warning: SPF_field_bitmask not present for devdef "+devf
                continue;
            
            dev['_SPFbm'] = [int(a) for a in dev['SPF_field_bitmask'].split(',')];
            dev['_SPFft'] = dev['SPF_field_types'].split(',');
            
            if ( len(dev['_SPFbm']) != len(dev['feeds']) ):
                print "Warning: SPF_field_bitmask not the same length as the number of feeds"
                continue;
            
            if ( len(dev['_SPFft']) != len(dev['feeds']) ):
                print "Warning: SPF_field_types not the same length as the number of feeds"
                continue;
            
            if len(btstr) > 2 and btstr[0:2] == '0x':
                bt = int(btstr[2:],16)
            else:
                bt = int(btstr);
            
            dev['_type'] = devf
            dev_BT_cache[bt] = dev
            print "\t0x%02X : "%bt+dev['name']    

def read_packet_timestamp(data):
    if len(data) >= 8: # minimum for sensor data message
        if ord(data[1]) == MT_SENSOR_DATA: # this is a sensor data packet
            (time,) = struct.unpack('<I',data[2:6])
            return time
    return None
            
populate_BT_cache();
last_scan = time.time()
def read_packet(data):
    global last_scan
    BT = ord(data[0])
    MT = ord(data[1])
    data = data[2:]
    
    if not BT in dev_BT_cache:
        if time.time() - last_scan > 10:
            populate_BT_cache()
            if not BT in dev_BT_cache:
                return None;
            last_scan = time.time()
        else:
            return None
            
    feedidxfound = []
    feedvalsfound = []
    dev = dev_BT_cache[BT]
    devf = dev['_type']
    if MT == MT_SENSOR_DATA:
        (time,fields) = struct.unpack('<IH',data[0:6])
        data = data[6:]
        feedidx = 0;
        #print "Fields:%04X data:%s"%(fields,utils.hexify(data))
        # check each bit in <fields> and unpack from <data>
        for b in range(16): 
            if ( fields & (1<<b) != 0):
                while feedidx < len(dev['_SPFbm']):
                    #print "b=%d feedidx=%d"%(b,feedidx)
                    if dev['_SPFbm'][feedidx] > b:
                        print "Error: bitmask algorithm failed (is SPF_field_bitmask specified correctly? and in order?)"
                        print "\tb=%d (0x%02X), feedidx=%d [%s] SPFbm=%d"%(b,(1<<b),feedidx,dev['feeds'][feedidx],dev['_SPFbm'][feedidx])
                        break;
                    elif dev['_SPFbm'][feedidx] == b:
                        #print "\t[%s]"%(dev['feeds'][feedidx])
                        feedidxfound += [feedidx]
                        type = dev['_SPFft'][feedidx]
                        tsize = struct.calcsize(type);
                        (val,) = struct.unpack('<'+type,data[0:tsize])
                        data = data[tsize:]
                        feedvalsfound += [float(val)]
                        break;
                    
                    feedidx += 1
        
        # debugging
        #print "Data found: t=%10d fields=%04X"%(time,fields)
        #for fi in feedidxfound:
        #    print "\tFeed %d : %s => %8.2e"%(fi,dev['feeds'][feedidxfound[fi]],feedvalsfound[fi])
            
        return (devf,MT_SENSOR_DATA,time,feedidxfound,feedvalsfound)
        
def timesync_packet():
    return '\x00\x00'+struct.pack('<I',time.time())