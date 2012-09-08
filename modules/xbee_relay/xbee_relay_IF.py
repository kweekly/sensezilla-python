#!/usr/bin/python

import os,sys, re
import time
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

unixIPC = unixIPC.UnixIPC()

def connect():
    unixIPC.run_client('',int(config.map['xbee_relay']['port']), remote_host=config.map['global']['host'])

def register_as_relay():
    cmd_msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
    cmd_msg.command = xbee_relay_cmd_pb2.XBee_Relay_Cmd.REGISTER_AS_RELAY
    unixIPC.send("xbee_relay_cmd_pb2",cmd_msg.SerializeToString())
    flush()     

def reconnect():
    unixIPC.reconnect();
    
def connected():
    return unixIPC.connected

def flush(): 
    unixIPC.waitForSend()
    
def tick():
    return unixIPC.tick()

SUCCESS = 1;
ADDRESS_NOT_FOUND = 2;
NETWORK_TIMEOUT = 3;

def proc_end():
    msgs = unixIPC.waitForRecv();
    if ( len(msgs) > 0 ):
        (typ,msg,client) = msgs[-1]
        if ( typ == 'xbee_relay_resp_pb2'):
            resp = xbee_relay_resp_pb2.XBee_Relay_Resp()
            resp.ParseFromString(msg)
            if ( resp.code == xbee_relay_resp_pb2.XBee_Relay_Resp.SUCCESS ):
                return SUCCESS
            elif ( resp.code == xbee_relay_resp_pb2.XBee_Relay_Resp.ADDRESS_NOT_FOUND ):
                return ADDRESS_NOT_FOUND
            elif ( resp.code == xbee_relay_resp_pb2.XBee_Relay_Resp.NETWORK_TIMEOUT ):
                return NETWORK_TIMEOUT
            
    return NETWORK_TIMEOUT
 
def publish(source, data):
    cmd_msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
    cmd_msg.command = xbee_relay_cmd_pb2.XBee_Relay_Cmd.PUBLISH_DATA
    cmd_msg.source = source;
    cmd_msg.data = data;
    unixIPC.send("xbee_relay_cmd_pb2",cmd_msg.SerializeToString())
    return proc_end();    

def forward(to, data):
    cmd_msg = xbee_replay_cmd_pb2.XBee_Relay_Cmd()
    cmd_msg.command = xbee_relay_cmd_pb2.XBee_Relay_Cmd.FORWARD_TO_XBEE
    cmd_msg.data = data
    unixIPC.send("xbee_relay_cmd_pb2",cmd_msg.SerializeToString())
    return proc_end();
    
def broadcast(data):   
    cmd_msg = xbee_replay_cmd_pb2.XBee_Relay_Cmd()
    cmd_msg.command = xbee_relay_cmd_pb2.XBee_Relay_Cmd.BROADCAST_TO_XBEE
    cmd_msg.data = data
    unixIPC.send("xbee_relay_cmd_pb2",cmd_msg.SerializeToString())
    return proc_end();
