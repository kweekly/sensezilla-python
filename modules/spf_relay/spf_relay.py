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
import publisher
import socket
import sensor_packet

PORT = int(config.map['spf_relay']['port'])
MAX_TIMESTAMP_ERROR = float(config.map['spf_relay']['max_timestamp_error'])

tcp_socket = None

connected = False
clients = []

class TVClient:
    def __init__(self,sock,addr):
        self.sock = sock
        self.address = addr
        self.rxbuffer = ''
        self.txbuffer = ''
        self.desynched = False
        self.ip = sock.getpeername()
        self.UID = None
        

def send_message(dest_client, message):
    dest_client.txbuffer += escape(message) + "\x0A"
        
def unescape(str):
    ret = ''
    escapenext = False
    for i in xrange(len(str)):
        if ord(str[i]) == 0x7D:
            escapenext = True
        else:
            if escapenext:
                ret += chr( ord(str[i]) ^ 0x20 )
                escapenext = False
            else:
                ret += str[i]
    return ret

def escape(str):
    ret = ''
    for i in xrange(len(str)):
        if ord(str[i]) == 0x7D or ord(str[i]) == 0x0A:
            ret += chr(0x7D)
            ret += chr(ord(str[i]) ^ 0x20)
        else:
            ret += str[i]
    return ret

def reconnect(print_errors = False):
    global tcp_socket, clients
    if print_errors:
        print "Opening Server socket on port %d"%PORT
        
    if tcp_socket == None:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        try:
            tcp_socket.bind(('',PORT))
        except socket.error, (errno,msg):
            if errno != 98 :
                raise
            else:
                print "Socket still in use"
                time.sleep(1)
                tcp_socket = None
                return
                
        tcp_socket.listen(5)
        tcp_socket.setblocking(0)
        clients = []

    
def tick():
    global tcp_socket, clients
    
    retval = []
    
    if tcp_socket:
        try: 
            new_conn,addr = tcp_socket.accept()
            new_conn.setblocking(0)
            client = TVClient(new_conn,addr)
            clients.append(client)
            
        except socket.error, (errno,msg):
            if errno != 10035 and errno != 11 : # Oh shiiiii server socket died (otherwise its just a "non-block" error)
                print "ERROR: Server socket gave problem "+msg
                tcp_socket = None
    
 
    if tcp_socket:
        for client in clients:
            try :
                if len(client.txbuffer) > 0:
                    txlen = client.sock.send(client.txbuffer)
                    client.txbuffer = client.txbuffer[txlen:]
                
                str = client.sock.recv(4096);
                if not str: # probably disconnected or something
                    try: # try to disconnect
                        client.sock.close();
                    except socket.error:pass
                    finally:
                        clients.remove(client);
                else:
                    client.rxbuffer += str
            except socket.error, (errno, msg) :
                if errno != 10035 and errno != 11 : # not just a "blocking socket" problem. remove socket then
                    try: # try to disconnect
                        client.sock.close()
                    except socket.error:pass
                    finally:
                        if client in clients:
                            clients.remove(client)
            
            idx = client.rxbuffer.find('\x0A')
            while idx != -1:
                chunk = client.rxbuffer[0:idx]
                client.rxbuffer = client.rxbuffer[idx+1:]
                if len(chunk) > 0 and chunk[-1] == '\x0D':
                    chunk = chunk[0:-1]
                
                if len(chunk) > 0:
                    retval.append((client,chunk))
                
                idx = client.rxbuffer.find('\x0A')
    else:
        reconnect()
                
    return retval;
                
   
############ START OF PROGRAM ##################
reconnect(print_errors = True)


while True:
    msgs = tick()
    for (client,msg) in msgs:
        # client=None means it was a UDP packet
        msg = unescape(msg)
        try:
            result = sensor_packet.read_packet(msg)
            if not result:
                continue
            devtype = result[0]
            msgtype = result[1]
            if msgtype == sensor_packet.MT_DEVICE_IDENTIFIER:
                idstr = result[3]
                print "Device %s reporting in"%idstr
                client.UID = idstr
            else:
                if client.UID:
                    uid = client.UID
                else:
                    uid = client.ip[0]
                    
                if msgtype == sensor_packet.MT_RECORDSTORE_DATA:
                    records = result[2]
                else:
                    records = [msg]
                
                for idx in range(len(records)-1,-1,-1):
                    last_rec = records[idx]
                    tm = sensor_packet.read_packet_timestamp(last_rec)
                    if tm:
                        break;                    
                
                if tm:
                    if abs(time.time() - tm) > MAX_TIMESTAMP_ERROR:
                        offset = tm - time.time()
                        for midx in range(len(records)):
                            tm2 = sensor_packet.read_packet_timestamp(records[midx])
                            if tm2:
                                records[midx] = sensor_packet.set_packet_timestamp(records[midx],tm2 - offset);                            
                                
                        client.desynched = True
                    else:
                        if client.desynched:
                            print "Client at %s synchronized"%uid
                        client.desynched = False
                
                for m in records:
                    if sensor_packet.read_packet_type(m) == sensor_packet.MT_DEVICE_IDENTIFIER:
                        r = sensor_packet.read_packet(m)
                        uid = r[3]
                        
                print "%d records from %s"%(len(records),uid)
                
                for m in records:
                    if sensor_packet.read_packet_type(m) != sensor_packet.MT_DEVICE_IDENTIFIER:
                        sensor_packet.publish(uid,m)
        except:
            import traceback
            traceback.print_exc();
    
    for client in clients:
        if client.desynched:
            send_message(client, sensor_packet.timesync_packet())
            client.desynched = False
    
    time.sleep(0.01);

