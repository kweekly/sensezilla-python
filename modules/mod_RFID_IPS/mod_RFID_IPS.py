#!/usr/bin/python

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
import struct
import serial

import socket
import traceback

def process_cmd(cmd):
    global sock_connected,s
    if ( len(cmd) < 3 ):
        print "Command is too short"
        return
        
    tag_reading_recieved = False
    tag_reading_map = {} # primary key = tag addr, secondary key = sensor addr, value = rssi value
    
    reader_addr_str = cmd[0:2]
    unknown_str = cmd[2]
    pos = 3
    while pos < len(cmd):
        length = ord(cmd[pos])
        subcmd = cmd[pos+1]
        if subcmd == '\x02':
            sensor_addr_str = cmd[pos+2:pos+4]
           # print "Reading from sensor "+utils.hexify(sensor_addr_str),
            pos2 = pos+4;
            while pos2 < pos+1+length:
                tag_addr_str = cmd[pos2:pos2+2]
                tag_rssi_str = cmd[pos2+2:pos2+4]
                (tag_rssi,) = struct.unpack(">h",tag_rssi_str)
                tag_reading_recieved = True
                if tag_addr_str not in tag_reading_map:
                    tag_reading_map[tag_addr_str] = {}
                
                tag_reading_map[tag_addr_str][sensor_addr_str] = tag_rssi
                
                #print " tag "+utils.hexify(tag_addr_str)+":%3ddbM"%tag_rssi,
                pos2 = pos2+4
                
            #print ""
            
        pos += length + 1
                

    if tag_reading_recieved:
        tlvstr = ''
        for key,val in tag_reading_map.iteritems():
            tlvstr += 'timestamp/%d'%int(time.time()+0.5)+'/driver/rfidloc_sinbb/device_id/%s/'%utils.hexify(key)
            for subkey,rssival in val.iteritems():
                tlvstr += 'Sensor %s RSSI(dBm)/%d/'%(utils.hexify(subkey),rssival)
            tlvstr += '\n'
            #print tlvstr,

        print tlvstr,
        if sock_connected:
            try:
                s.sendall(tlvstr);
            except:
                traceback.print_exc();
                try:
                    s.close()
                except:pass
                sock_connected = False

ser = serial.Serial(config.map['mod_RFID_IPS']['serial_port'],int(config.map['mod_RFID_IPS']['serial_speed']),timeout=0)
MAX_CMD_SIZE = int(config.map['mod_RFID_IPS']['max_cmd_size']);

HOST_NAME = config.map['global']['host']
HOST_PORT = int(config.map['tv_relay']['port'])

print "Connecting to %s port %d"%(HOST_NAME,HOST_PORT)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
try:
    s.connect((HOST_NAME,HOST_PORT))
    sock_connected = True
except:
    try:
        s.close()
    except:pass
    traceback.print_exc();
    sock_connected = False

cmdbuf = ''
recieving_cmd = False

while True:
    while True:
        b = ser.read(size=1)
        if len(b) == 0:
            break;
        b = b[0]
        if b == '\x7E':
            cmdbuf = ''
            recieving_cmd = True
        elif b == '\x7B':
            process_cmd(cmdbuf)
            recieving_cmd = False
        elif len(cmdbuf) >= MAX_CMD_SIZE:
            print "Buffer overflow!"
            cmdbuf = ''
            reciving_cmd = False
        elif recieving_cmd:
            cmdbuf += b
    
    if not sock_connected:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
            s.connect((HOST_NAME,HOST_PORT))
            sock_connected = True
        except:
            try:
                s.close()
            except:pass
            sock_connected = False
    
    time.sleep(0.1);
