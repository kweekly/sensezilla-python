#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys,os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime, timedelta

sys.argv = sys.argv[1:]

if ( len(sys.argv) == 0):
    print """
Usage: computationmanager.py [list | add]
    list
        Lists computations that are in the database
    
    add [--pretend] [--source name id]...[--source name id] <unique name> <csv file>
        Adds a computation to the database and publishes the csv file into the source
        --pretend : don't actually add anything to the database
        --source name id : Attaches metadata from this source/id pair
        
        

"""
    sys.exit(0);
    
op = sys.argv.pop(0)

import publisher, devicedb, postgresops


if ( op == 'list') :
    devicedb.connect();
    devs = devicedb.get_devices(where="device_type='computed'",orderby="source_name ASC,idstr ASC");
    cur_sname = ''
    for dev in devs:
        if dev.source_name != cur_sname:
            cur_sname = dev.source_name;
            print "Source \""+cur_sname+"\""
        
        print "\t%20s : "%dev.IDstr,
        if len(dev.source_ids) > 0:
            print dev.source_ids[0]
            for i in dev.source_ids[1:]:
                print "\t%20s : %s"%('',i)
        print;
    
elif (op == 'add'):
    pretend,j,sys.argv = utils.check_arg(sys.argv,'--pretend')
    
    snames = []
    sids = []
    while True:
        ret,vals,sys.argv = utils.check_arg(sys.argv,'--source',2);
        if not ret:
            break;
            
        snames.append(vals[0])
        sids.append(vals[1])
        
    metadatas=[]
    devicedb.connect()
    fail = False;
    for i in range(len(snames)):
        sname = snames[i]
        sid = sids[i]
        postgresops.check_evil(sname);
        postgresops.check_evil(sid);
        devs = devicedb.get_devices(where="source_name='%s' and '%s'=any(source_ids)"%(sname,sid),limit=1);
        if ( len(devs) == 0 ):
            print "Error: Cannot find %s,%s in devicedb"%(sname,sid)
            fail = True;
            continue;
            
        metadev = devicedb.get_devicemetas(where="%d=any(devices)"%devs[0].ID);
        for m in metadev[:]:
            if ( m.key.startswith('PLUGLOAD')):
                metadev.remove(m)
                
        print "Found %d metadata entries for source/id=%s/%s (device: %s)"%(len(metadev),sname,sid,devs[0].IDstr)
        metadatas.extend(metadev)
        
    if fail:
        sys.exit(1);
    
    compname = sys.argv.pop(0)
    csvfname = sys.argv.pop(0)
    
    timel = []
    csvdata,meta,headers = utils.readcsv(csvfname, readmeta=True,readheader=True);
    #transpose row-major into column-major
    csvdata = map(list, zip(*csvdata))
    
    if headers == None:
        headers = ['t'] + [str(i) for i in range(len(csvdata)-1)]
        
    timel = csvdata.pop(0)
    headers.pop(0)
    headers = [s.lstrip().rstrip() for s in headers]
    
    print "Read %d"%len(timel)+" points in %d columns."%(len(csvdata))
    
    devdef = utils.read_device('computed')
    devdef['feeds'] = headers;
    
    feeds_present = False
    
    dev = publisher.find_device(compname, create_new=not pretend, device_type='computed',  devdef=devdef )
    if dev:
        print "Found/created device "+dev.IDstr
        for m in metadatas[:]:
            if m.key.startswith("ALTFEEDNAME"):
                feeds_present = True
                
            if dev.ID in m.devices:
                metadatas.remove(m)

        if not feeds_present:
            for hi in range(len(headers)):
                m = devicedb.new_devicemeta()
                m.key = "ALTFEEDNAME%d"%hi
                m.value = headers[hi]
                m.devices = [dev.ID]
                if not pretend:
                    devicedb.insert_devicemeta(m)

        if len(metadatas) > 0 and not pretend:             
            postgresops.dbcur.execute("UPDATE devices.metadata set devices = devices || %s where id=any(%s)",(dev.ID,[m.ID for m in metadatas]))
            postgresops.dbcon.commit();
            
        print "Updated %d metadata entries"%(len(metadatas)+(len(headers) if not feeds_present else 0))
        
    
    if not pretend:
        print "Publishing..."
        publisher.publish_data(compname,timel,csvdata,devdef=devdef, device_type='computed')
    
    if not pretend:
        print "Flushing..."
        publisher.flush();
    
else:
    print "Unknown command "+op
    sys.exit(1);
    
    
    