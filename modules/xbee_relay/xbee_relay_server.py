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

import struct

import publisher
import sensor_packet

server = unixIPC.UnixIPC();
server.run_server(False, int(config.map['xbee_relay']['port']));

xbee_addr_to_relay_clients_map = {}
message_tracking_map = {}
relay_clients = []
global_seq_no = 0

client_response_map = {}

CACHE_TIMEOUT = 100


def broadcast(data):
    global global_seq_no
    msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
    msg.command = BROADCAST_TO_XBEE
    msg.data = data
    msg.seq_no = global_seq_no
    global_seq_no += 1
    for client in relay_clients:
        unixIPC.sendTo('xbee_relay_cmd_pb2', msg, client)
    return msg.seq_no
    

def sendToXbee(xbee_addr, data):
    global global_seq_no
    msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
    msg.command = FORWARD_TO_XBEE
    msg.data = data
    msg.to = xbee_addr
    msg.seq_no = global_seq_no
    global_seq_no += 1
    if ( xbee_addr in xbee_addr_to_relay_clients_map ):
        unixIPC.sendTo('xbee_relay_cmd_pb2',msg,xbee_addr_to_relay_clients_map[xbee_addr])
        message_tracking_map[(msg.seq_no,xbee_addr_to_relay_clients_map[xbee_addr])] = (xbee_addr, time.time());
    else:
        for client in relay_clients:
            unixIPC.sendTo('xbee_relay_cmd_pb2', msg, client)
            message_tracking_map[(msg.seq_no,client)] = (xbee_addr, time.time());
            
    return msg.seq_no

def unpack_several(data, offset=0, numfields=1, datatype='l', endian='<'):
    return struct.unpack_from(endian+datatype*numfields,data,offset)
    

def publish(source, data):
    print "Publish from %s data %s"%(source,utils.hexify(data))
    try:
        SPF_result = sensor_packet.read_packet(data)
    except struct.error, emsg:
            print "Error parsing SPF packet from %s device (%s): %s"%(dev.device_type,str(emsg),utils.hexify(data))

    if SPF_result != None:
        if SPF_result[1] == sensor_packet.MT_SENSOR_DATA:
            (devname,packet_type,time,feedidxfound,feedvalsfound) = SPF_result
            devdef = utils.read_device(devname);
            dev = publisher.find_device(source, create_new=True, device_type=devname, devdef=devdef )
            dev.feed_names = devdef['feeds']
            publisher.publish_data(source, time, feedvalsfound, feednum=feedidxfound, device_type=devname, dev=dev)
        elif SPF_result[1] == sensor_packet.MT_RFID_TAG_DETECTED:
            (devname,packet_type,time,uidstr) = SPF_result
            devdef = utils.read_device(devname);
            dev = publisher.find_device(uidstr, create_new=True, device_type=devname, devdef=devdef )
            sourcestr = "RFID Reader %s"%source
            if ( sourcestr in dev.feed_names ):
                idx = dev.feed_names.index(sourcestr)
                feedidxfound = idx
            else:
                dev.feed_names.append(sourcestr)
                feedidxfound = len(dev.feed_names)-1
                
            feedvalfound = 1.0;
            publisher.publish_data(uidstr, time, feedvalfound, feednum=feedidxfound, device_type=devname, dev=dev)
        
try:
    while True:
        if server.connected:
            msgs = server.tick();
            for typ,msg,client in msgs:
                if typ=='xbee_relay_cmd_pb2':
                    cmd_msg = xbee_relay_cmd_pb2.XBee_Relay_Cmd()
                    cmd_msg.ParseFromString(msg);
                    if ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.PUBLISH_DATA ):
                        publish(cmd_msg.source, cmd_msg.data)
                    elif ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.FORWARD_TO_XBEE ):
                        seq_no = sendToXbee(cmd_msg.to,cmd_msg.data)
                        client_response_map[seq_no] = (client,time.time())
                    elif ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.BROADCAST_TO_XBEE ):
                        seq_no = broadcast(cmd_msg.data)
                        client_response_map[seq_no] = (client,time.time())
                    elif ( cmd_msg.command == xbee_relay_cmd_pb2.XBee_Relay_Cmd.REGISTER_AS_RELAY ):
                        print "XBee Relay at ",client.ip," added"
                        relay_clients.append(client)
                    else:
                        print "Unknown command code"
                elif typ=='xbee_relay_resp_pb2':
                    resp_msg = xbee_relay_resp_pb2.XBee_Relay_Resp()
                    resp_msg.ParseFromString(msg);
                    if ( (resp_msg.seq_no,client) in message_tracking_map ):
                        xbee_addr = message_tracking_map.pop((resp_msg.seq_no,client))[0]
                        if ( resp_msg.code == xbee_relay_resp_pb2.XBee_Relay_Resp.SUCCESS ):
                            xbee_addr_to_relay_clients_map[xbee_addr] = client;
                            if resp_msg.seq_no in client_response_map:
                                if ( unixIPC.clientConnected(client_response_map[resp_msg.seq_no][0])):
                                    unixIPC.sendTo('xbee_relay_resp_pb2',msg,client_response_map.pop(resp_msg.seq_no)[0])
                        elif ( resp_msg.code != xbee_relay_resp_pb2.XBee_Relay_Resp.SUCCESS and 
                               xbee_addr in xbee_addr_to_relay_clients_map and xbee_addr_to_relay_clients_map[xbee_addr] == client ):
                            xbee_addr_to_relay_clients_map.pop(xbee_addr)
                            
                else:
                    print "Unknown command "+typ
        else:
            server.reconnect();
           
        # timeouts
        rmkeys = set()
        for (seq_no,val) in client_response_map.iteritems():
            if ( time.time() > val[1] + CACHE_TIMEOUT ):
                rmkeys.add(seq_no)
                
        for key in rmkeys:
            client_response_map.pop(key)
        
        rmkeys.clear()
        for (key,val) in message_tracking_map.iteritems():
            if ( time.time() > val[1] + CACHE_TIMEOUT ):
                if val[0] in xbee_addr_to_relay_clients_map and xbee_addr_to_relay_clients_map[val[0]] == key[1]:
                    xbee_addr_to_relay_clients_map.pop(val[0])
                rmkeys.add(key)
                
        for key in rmkeys:
            message_tracking_map.pop(key)
        

        publisher.tick();        

        time.sleep(0.1)
except:
        import traceback
        print "ERROR OCCURED:"
        traceback.print_exc()
    
print "Closing server socket"
server.close()
