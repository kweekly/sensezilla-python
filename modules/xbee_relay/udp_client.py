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
import socket

import google.protobuf
import xbee_relay_cmd_pb2
import xbee_relay_resp_pb2

import xbee_relay_IF
from xbee_utils import *
import sensor_packet

xbee_relay_IF.connect();
xbee_relay_IF.register_as_relay();

udp_socket = None
PORT = int(config.map['xbee_relay']['udp_port'])

def reconnect(print_errors = False):
    global clients, udp_socket
    if print_errors:
        print "Opening Server socket on port %d"%PORT
        
    if udp_socket == None:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('',PORT))
        udp_socket.setblocking(0)


 
def tick():
    global clients, udp_socket
    
    retval = []

    if udp_socket:
        str = ''
        try:
            str,addr = udp_socket.recvfrom(1024)
        except socket.error, (errno, msg) :
            if errno != 10035 and errno != 11 : # not just a "blocking socket" problem. remove socket then
                import traceback
                traceback.print_exc();
            
        idx = str.find('\x0A')
        while idx != -1:
            chunk = str[0:idx]
            str = str[idx+1:]
            
            if len(chunk) > 0 and chunk[-1] == '\x0D':
                chunk = chunk[0:-1]
            
            if len(chunk) > 0:
                # replace 7DXX with XX^0x20
                while True:
                    i = chunk.find("\x7D")
                    if ( i == -1 ): break;
                    chunk = chunk[0:i] + chr(ord(chunk[i+1])^0x20) + chunk[i+2:]
            
                retval.append((addr[0],chunk))               
            
            idx = str.find('\x0A')
    else:
        reconnect()
        
    return retval
       

reconnect(True);       
while True:
    # process connection to relay server
    if xbee_relay_IF.connected():
        msgs = xbee_relay_IF.tick()
    else:
        xbee_relay_IF.reconnect();
        if xbee_relay_IF.connected():
            xbee_relay_IF.register_as_relay();
        
    # process connection w/ remotes
    msgs = tick()
    for addr,chunk in msgs:
        print "<",addr,utils.hexify(chunk)
        chunk = sensor_packet.set_packet_timestamp(chunk,time.time())
        
        if xbee_relay_IF.connected():
            xbee_relay_IF.publish(addr,chunk)
                        

    time.sleep(0.01);

    
    
