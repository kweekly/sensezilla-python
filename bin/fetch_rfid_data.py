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
Usage: fetch_rfid_data.py <rssi system file> <output directory>
"""
    sys.exit(0);
    
rssi_sysfile = os.path.normpath(sys.argv[1])
outdir = sys.argv[2]
sysfile_relpath = os.path.relpath(rssi_sysfile,outdir);

import devicedb
import postgresops

devicedb.connect()
if not devicedb.connected():
    print "Error: cannot connect to devicedb";
    sys.exit(1);
    
tempmap = config.map
config.map = {}
config.load_conf(rssi_sysfile)
rssimap = config.map
config.map = tempmap

