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
from xbee.ieee import XBee

import xbee_relay_IF
from xbee_utils import *


BROADCAST_SINK = float(config.map['xbee_relay']['broadcast_sink'])

xbee_relay_IF.connect();
xbee_relay_IF.register_as_relay();

ser = serial.Serial(SERIAL_PORT,int(config.map['xbee_relay']['serial_speed']))
xbee = XBee(ser, callback=frame_recieved, escaped=True)


 
init_xbee(ser, xbee);

children_cache = set()

CMD_TIME_SYNC = '\x01';

ts_sent_update = {}
ts_updated = set()
ts_noupdate = set()

def ts_send(addr):
    global ts_sent_update, ts_updated, ts_noupdate
    if addr in ts_noupdate:
        return;
    print "Sending Timesync message to "+addr
    curtime = time.time();
    send_to_xbee(addr, CMD_TIME_SYNC + struct.pack('<I',int(curtime)) )
    ts_sent_update[addr] = curtime;


def send_to_xbee(dest, data):
    global children_cache
    
    if not SEND_ONLY_TO_CACHE or dest in children_cache or dest == '000000000000FFFF':
        xbee.send('tx_long_addr',dest_addr=utils.unhexify(dest),data=data)
        return True
    else:
        return False

last_sim_send = time.time()
last_broadcast_sink = time.time()

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
                            xbee.send('tx_long_addr',dest_addr='\x00\x00\x00\x00\x00\x00\xFF\xFF',data=cmd_msg.data)
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
            #print "FRAME "+frame['id']
            if frame['id'] == 'at_response':
                pass
            elif frame['id'] == 'tx_status':
                pass
            elif frame['id'] == 'rx_long_addr' or frame['id'] == 'rx_io_data_long_addr':
                source_addr = utils.hexify(frame['source_addr'])
                if frame['id'] == 'rx_long_addr':
                    data = frame['rf_data']
                else:
                    tdata = frame['samples']
                    data = "DIGI/"
                    for delem in tdata:
                        print delem
                        for key,val in delem.iteritems():
                            data += str(key)+"/"+str(val)+"/"
                    print "Digi data: "+data
                    ts_noupdate.add(source_addr)
                
                #print "<"+source_addr+" : "+utils.hexify(data)
                children_cache.add(source_addr)

                rtime = 0
                if len(data) >= 4 and source_addr not in ts_noupdate:
                    rtime, = struct.unpack('<L',data[0:4])
                    if time.time() - rtime <= MAX_TIMESTAMP_ERROR:
                        if source_addr not in ts_updated:
                            print "Device at "+source_addr+" synced."
                            ts_updated.add(source_addr)
                            if source_addr in ts_sent_update:
                                ts_sent_update.pop(source_addr)
                    else:
                        if source_addr in ts_updated:
                            print "Device at "+source_addr+" desynced."
                            ts_updated.remove(source_addr)

                if xbee_relay_IF.connected():
                    xbee_relay_IF.publish(source_addr,data)
                        
                if ( source_addr not in ts_updated and source_addr not in ts_sent_update  ):
                    ts_send(source_addr)
            else:
                print "Don't know what to do with frame type=",frame['id']
            
        for source,stime in ts_sent_update.items():
	    #print source,stime
            if time.time() - stime > MAX_TIMESTAMP_ERROR:
                ts_send(source)
            
            
        if time.time() - last_broadcast_sink > BROADCAST_SINK:
            ts_send("000000000000FFFF")
            last_broadcast_sink = time.time()
         # simulation
        #if ( time.time() > last_sim_send + 1 and xbee_relay_IF.connected()):  
        #    xbee_relay_IF.publish("13A20040771205","\x01"*(4*(12+1)))
        #    last_sim_send = time.time()
        
        time.sleep(0.01);
finally:
    xbee.halt()
    ser.close()
    
