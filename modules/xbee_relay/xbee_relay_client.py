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

import google.protobuf
import xbee_relay_cmd_pb2
import xbee_relay_resp_pb2

import serial
from xbee import XBee, ZigBee

import xbee_relay_IF
from xbee_utils import *

xbee_relay_IF.connect();
xbee_relay_IF.register_as_relay();

ser = serial.Serial(SERIAL_PORT,int(config.map['xbee_relay']['serial_speed']))
xbee = ZigBee(ser, callback=frame_recieved)
 
init_xbee(ser, xbee);

children_cache = set()

CMD_TIME_SYNC = '\x01';


ts_sent_update = {}
ts_updated = set()
def ts_received(source,dat):
    rtime, = struct.unpack('<I')
    if ( time.time() - rtime > MAX_TIMESTAMP_ERROR ):
        print "Device at "+addr+" got timesync, but is %d seconds off"%(time.time()-rtime)
        ts_send(source)
    else:
        print "Device at "+addr+" synced"
        ts_updated.add(source)
        if source in ts_sent_update:
            ts_sent_update.pop(source)

def ts_send(addr):
    print "Sending Timesync message to "+addr
    curtime = time.time();
    send_to_xbee(addr, CMD_TIME_SYNC + struct.pack('<I',int(curtime)) )
    ts_sent_update[addr] = curtime;


def send_to_xbee(dest, data):
    global children_cache
    
    if not SEND_ONLY_TO_CACHE or dest in children_cache:
        xbee.send('tx',dest_addr_long=utils.unhexify(dest),data=data)
        return True
    else:
        return False

last_sim_send = time.time()

try:
    while True:
        # process connection to relay server
        if xbee_relay_IF.connected():
            msgs = xbee_relay_IF.tick()
            for typ,msg,client in msgs:
                if typ == 'xbee_relay_cmd_pb2':
                    cmd_msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
                    cmd_msg.ParseFromString(msg);
                    if ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.FORWARD_TO_XBEE ):
                        if send_to_xbee(cmd_msg.to.upper(), cmd_msg.data):
                            pass
                        else:
                            resp = xbee_relay_resp_pb2.XBee_Relay_Resp()
                            resp.seq_no = cmd_msg.seq_no
                            resp.cod = xbee_relay_resp_pb2.XBee_Relay_Resp.ADDRESS_NOT_FOUND
                    elif ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.BROADCAST_TO_XBEE ):
                        if IEEE_BROADCAST:
                            xbee.send('tx',dest_addr='\xFF\xFF',data=cmd_msg.data)
                        else:
                            for d in children_cache:
                                send_to_xbee(d,cmd_msg.data)
                    else:
                        print "Unknown command code"
                elif typ == 'xbee_relay_resp_pb2':
                    resp_msg = xbee_relay_resp_pb2.XBee_Relay_Resp()
                    resp_msg.ParseFromString(msg);
                else:
                    pass
        else:
            xbee_relay_IF.reconnect();
            if xbee_relay_IF.connected():
                xbee_relay_IF.register_as_relay();
            
        # process connection w/ XBee
        while len(xbee_frames) > 0:
            frame = xbee_frames.pop();
            if frame['id'] == 'at_response':
                pass
            elif frame['id'] == 'tx_status':
                pass
            elif frame['id'] == 'rx':
                source_addr = utils.hexify(frame['source_addr_long'])
                data = frame['rf_data']
                if ( data[0] == CMD_TIME_SYNC and len(data) == 5 ):
                    ts_recieved(source_addr,data[1:])
                else:
                    xbee_relay_IF.publish(source_addr,data)
                    if ( source_addr not in ts_updated and source_addr not in ts_sent_update  ):
                        ts_send(source_addr)
                    
                children_cache.add(source_addr)
            else:
                print "Don't know what to do with frame type=",frame['id']
            
        for source,stime in ts_sent_update.iteritems():
            if time.time() - stime > MAX_TIMESTAMP_ERROR:
                ts_send(source)
            
         # simulation
        #if ( time.time() > last_sim_send + 1 and xbee_relay_IF.connected()):  
        #    xbee_relay_IF.publish("13A20040771205","\x01"*(4*(12+1)))
        #    last_sim_send = time.time()
        
        time.sleep(0.01);
finally:
    xbee.halt()
    ser.close()
    
