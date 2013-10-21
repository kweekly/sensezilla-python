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

PORT = int(config.map['tv_relay']['port'])

tcp_socket = None
udp_socket = None

connected = False
clients = []

class TVClient:
    def __init__(self,sock,addr):
        self.sock = sock
        self.address = addr
        self.rxbuffer = ''
        self.txbuffer = ''
        self.ip = sock.getpeername()
        

def reconnect(print_errors = False):
    global tcp_socket, clients, udp_socket
    if print_errors:
        print "Opening Server socket on port %d"%PORT
        
    if tcp_socket == None:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        tcp_socket.bind(('',PORT))
        tcp_socket.listen(5)
        tcp_socket.setblocking(0)
        clients = []
        
    if udp_socket == None:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('',PORT))
        udp_socket.setblocking(0)
    
def tick():
    global tcp_socket, clients, udp_socket
    
    retval = []
    
    try:
        new_conn,addr = tcp_socket.accept()
        new_conn.setblocking(0)
        clients.append(TVClient(new_conn,addr))
    except socket.error, (errno,msg):
        if errno != 10035 and errno != 11 : # Oh shiiiii server socket died (otherwise its just a "non-block" error)
            print "ERROR: Server socket gave problem "+msg
            tcp_socket = None
    
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
                retval.append((None,chunk))               
            
            idx = str.find('\x0A')
        
    else:
        reconnect()

    
    if tcp_socket:
        for client in clients:
            try :
                str = client.sock.recv(4096);
                print str
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
                
def parse_tv_string(str):
    keyvals = {}
    pts = str.split('/');
    for i in reversed(range(len(pts))):
        if len(pts[i]) == 0 : pts.pop(i);
    
    if len(pts) <= 1:
        return keyvals
    
    if len(pts) % 2 != 0:
        val = pts.pop(len(pts)-1)
        print "WARNING: Last value '%s' of TV string discarded (odd number of fields)."%val
    
    for i in range(0,len(pts),2):
        #print pts[i],pts[i+1]
        keyvals[pts[i]] = pts[i+1];
        
    return keyvals
    
def publish_data( keyvals, msg_dbg=''):    
    if keyvals != None  and 'driver' in keyvals and 'device_id' in keyvals:
        driver = keyvals['driver']
        device_id = keyvals['device_id']
        devdef = utils.read_device(driver)
        if devdef == None:
            print "Device definition for %s not found"%driver
            return

        ## Custom device drivers here
        if driver == 'custom!@#!@$!$#':
            pass
        else: # generic driver: try to match keys to feeds
            if 'timestamp' in keyvals:
                dev = publisher.find_device( device_id, create_new=True, device_type=driver, devdef=devdef )
                
                ts = utils.date_to_unix(utils.str_to_date(keyvals['timestamp']))
                datapoints = []
                feednums = []
                
                for key,val in keyvals.iteritems():
                    if key in ['driver','device_id','timestamp']:
                        continue
                        
                    try:
                        f = float(val);
                    except:
                        print "Skipping Key-Value pair",key,"/",val,"as it is non-numeric"
                        continue;
                        
                    if key in dev.feed_names:
                        idx = dev.feed_names.index(key)
                        feednums.append(idx)
                        datapoints.append(f)
                    else:
                        feednums.append(len(dev.feed_names))
                        datapoints.append(f)
                        dev.feed_names.append(key)
                try:
                    if (len(datapoints) > 0):
                        publisher.publish_data( device_id, ts, datapoints, feednum=feednums, devdef=devdef, device_type=driver, dev=dev)
                except:
                    import traceback
                    traceback.print_exc();
            else:
                print "Data Line '%s' did not have a timestamp field (for generic driver)"%msg_dbg
        
        
    else:
        print "Data Line '%s' did not contain a key for driver and/or device_id"%msg_dbg
    
############ START OF PROGRAM ##################
reconnect(print_errors = True)


while True:
    msgs = tick()
    for (client,msg) in msgs:
        # client=None means it was a UDP packet
        keyvals = parse_tv_string(msg);
        try:
            if len(msg) > 100: # trim large messages for debug
                msg = msg[0:100]
                
            publish_data(keyvals,msg_dbg = msg)
        except:
            import traceback
            traceback.print_exc();
        
    publisher.tick();
    time.sleep(0.1);

