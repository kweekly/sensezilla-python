#!/usr/bin/python

import os,sys, re

if len(sys.argv) == 1:
    print "Usage: init_xbee.py <serial port> [mission]\nInitializes XBEE for use w/ Sensezilla\n"
    sys.exit(1);
    
if ( len(sys.argv) >= 3):
    os.environ['SENSEZILLA_MISSION'] = sys.argv[2]

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
from xbee_relay.xbee_utils import *
import serial
from xbee import XBee, ZigBee

xbee = None
try:
    ser = serial.Serial(sys.argv[1],int(config.map['xbee_relay']['serial_speed']))
    xbee = ZigBee(ser, callback=frame_recieved)

    init_xbee(ser, xbee);
    xbee.halt();
except:
    if xbee:
        xbee.halt();
    raise