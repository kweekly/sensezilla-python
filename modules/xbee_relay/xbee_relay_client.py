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

import google.protobuf
import xbee_relay_cmd_pb2
import xbee_relay_resp_pb2

import serial
from xbee import XBee, ZigBee

import xbee_relay_IF

xbee_relay_IF.connect();
xbee_relay_IF.register_as_relay();

(COORDINATOR,ROUTER,END_DEVICE) = range(3)

XBEE_TYPE = config.map['xbee_relay']['xbee_type']
if XBEE_TYPE.upper() == 'COORDINATOR':
    XBEE_TYPE = COORDINATOR
elif XBEE_TYPE.upper() == 'ROUTER':
    XBEE_TYPE = ROUTER
elif XBEE_TYPE.upper() == 'END_DEVICE':
    XBEE_TYPE = END_DEVICE
else:
    print "xbee_type cannot be ",XBEE_TYPE
    XBEE_TYPE = ROUTER

DRIVER = config.map['xbee_relay']['driver']
if DRIVER == 'beagleboard':
    def do_cmd(cmd):
        print cmd
        os.system(cmd);
        
    do_cmd('echo 20 > /sys/kernel/debug/omap_mux/uart1_rxd')
    do_cmd('echo 0 > /sys/kernel/debug/omap_mux/uart1_txd')
    
    SERIAL_PORT = '/dev/ttyS1'
elif DRIVER == 'direct' or True:
    SERIAL_PORT = config.map['xbee_relay']['serial_port']
    
AT_COMMANDS = config.map['xbee_relay']['at_cmds']

SEND_ONLY_TO_CACHE = True if config.map['xbee_relay']['send_only_to_cache'].lower() == 'true' else False
IEEE_BROADCAST = True if config.map['xbee_relay']['ieee_broadcast'].lower() == 'true' else False


xbee_frames = []
def frame_recieved(data):
    global xbee_frames
    print "Frame recieved: ",data
    #if ( data.has_key('parameter')):
        #print "Parameter: "+utils.hexify(data['parameter'])
    xbee_frames.append(data)

ser = serial.Serial(SERIAL_PORT,int(config.map['xbee_relay']['serial_speed']))
xbee = ZigBee(ser, callback=frame_recieved)

def read_at(atcmd):
    global xbee_frames
    xbee_frame_pos = len(xbee_frames);
    xbee.send('at',command=atcmd)
    start = time.time()
    while time.time() < start + 2:
        if len(xbee_frames) > xbee_frame_pos:
            for i in range(xbee_frame_pos,len(xbee_frames)):
                if xbee_frames[i]['id'] == 'at_response' and xbee_frames[i]['command'] == atcmd:
                    if xbee_frames[i].has_key('parameter'):
                        return xbee_frames.pop(i)['parameter']
                    else:
                        print "ERROR invalid AT command",atcmd
                        return None
    
    print "ERROR Read AT Timeout"
    return None

def verify_at(atcmd, value):
    val = read_at(atcmd)
    if val != None and val != value and utils.strip0s(value) != utils.strip0s(val):
        print "%s Command expected %s got %s"%(atcmd,utils.hexify(value),utils.hexify(val))
        xbee.send('at',command=atcmd,parameter=value)
        return False
    return True

def init_xbee():
    something_changed = False
    
    if XBEE_TYPE == ROUTER:
        if verify_at("SM","\x00"): something_changed = True
    elif XBEE_TYPE == END_DEVICE:
        if verify_at("SM","\x04"): something_changed = True
    
    
    for cval in AT_COMMANDS:
        try:
            cmd,val = cval.split(',')
            
            if ( len(val) > 2 and val.startswith('0x') ):
                sstr = utils.unhexify(val[2:])
            elif (len(val) > 2 and val.startswith('0d')):
                sstr = utils.undecify(int(val[2:]))
            else:
                sstr = val
        except Exception,e:
            print "Error parsing AT Command",cmd," value ",sstr," : ",e
            
        if verify_at(cmd,sstr):
            something_changed = True

    if something_changed:
        xbee.send('at',command='WR')
    
    
init_xbee();

children_cache = set()
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
                xbee_relay_IF.publish(source_addr,data)
            else:
                print "Don't know what to do with frame type=",frame['id']
            
         # simulation
        if ( time.time() > last_sim_send + 1 and xbee_relay_IF.connected()):  
            xbee_relay_IF.publish("13A20040771205","\x01"*(4*(12+1)))
            last_sim_send = time.time()
        
        time.sleep(0.01);
finally:
    xbee.halt()
    ser.close()
    
