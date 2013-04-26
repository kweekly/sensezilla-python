#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys,os, time, os.path, shutil
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime, timedelta

if len(sys.argv) < 3:
    print """
Usage: fetch_rfid_data.py <rssi system file> <output directory> [--from <fromtime>] [--to <totime>] [--pretend] [--metaonly]
"""
    sys.exit(0);
    
(has_ftime, fromtime, sys.argv) = utils.check_arg(sys.argv,'--from',1)
fromtime = fromtime[0]
(has_totime, totime, sys.argv) = utils.check_arg(sys.argv,'--to',1)
totime = totime[0]
(pretend,a,sys.argv) = utils.check_arg(sys.argv,'--pretend')
(metaonly,a,sys.argv) = utils.check_arg(sys.argv,'--metaonly')

rssi_sysfile = os.path.normpath(sys.argv[1])
outdir = sys.argv[2]
sysfile_relpath = os.path.relpath(rssi_sysfile,outdir);

import devicedb
import postgresops

devicedb.connect()
if not devicedb.connected():
    print "Error: cannot connect to devicedb";
    sys.exit(1);
    
if not pretend:
    try:
        os.makedirs(outdir)
    except:pass
    fptr = open(outdir+'/rssiparam.conf','w');
    fptr.write('# this file automatically generated by fetch_rfid_data.py\n');
    fptr.write('include "%s"\n\n'%sysfile_relpath);
    fptr.write('[rssidata]\n')
    
rssimap = config.load_separate_conf(rssi_sysfile)
for referenceID in rssimap['tags']['reference_list']:
    print "\nLooking for data for tag:"+referenceID
    postgresops.check_evil(referenceID)
    dev = devicedb.get_devices(where="idstr='%s' and device_type like 'rfidloc%%'"%referenceID,limit=1)
    if ( len(dev) == 0 ):
        print "\tDevice not found in db";
        continue;
    dev = dev[0]
    for sensorID in rssimap['sensors']['active_list']:
        print "\tSensor "+sensorID,
        fidx = -1
        for feedi in range(1,len(dev.feed_names)):
            if sensorID in dev.feed_names[feedi]:
                fidx = feedi
                break
                
        datfname = "%s/RSSI_t%s_s%s.csv"%(outdir,referenceID,sensorID);
        datfname_relpath = os.path.relpath(datfname,outdir)
        if not pretend:
            fptr.write('%s_%s = %s\n'%(referenceID,sensorID,datfname_relpath))
        
        if fidx == -1:
            print "NOT FOUND"
            if not pretend and not metaonly:
                fout = open("%s"%datfname,"w");
                fout.close();
        else:
            print dev.source_name+":"+dev.source_ids[fidx]
            
            if not metaonly:
                cmd = "fetcher.py fetch "+dev.source_name+" "+dev.source_ids[fidx]+" " + datfname
                if has_ftime:
                    cmd += " --from "+fromtime
                if has_totime:
                    cmd += " --to "+totime
                    
                print "\t\t"+cmd
                if not pretend:
                    os.system(cmd)
                    
if not pretend:
    fptr.close()
        