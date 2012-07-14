# -*- coding: utf-8 -*-
import sys,os,time
import socket
import config

BAD_HEADER_TOLERANCE = 3;
ID = None

class UnixIPC:
    class IPCClient:pass
    
    def __init__(self):
        self.clients = []
        self.connected = False
        self.mod_name = "error";
        self.win32port = 8001;
        try:
            idx = sys.argv.index("-sid")
        except:
            idx = -1
            
        if idx != -1:
            self.ID = sys.argv[idx+1]
        elif ID != None:
            self.ID = ID
        else:
            self.ID = None
        
        if self.ID != None:
            self.IDprefix = True
            print "Prefix mode on. Using "+self.ID
        else:
            self.IDprefix = False
        
        

    def run_server(self, mod_name, win32port=8001):
        self.mod_name = mod_name;
        self.win32port = win32port;
        #global server_socket,mode,connected
        self.mode="server"
        self.reconnect(print_errors=True);

 
    def run_client(self, mod_name, win32port=8001, remote_host="127.0.0.1"):
        #global mode,connected
        self.mode = "client"
        self.mod_name = mod_name
        self.remote_host = remote_host
        self.win32port = win32port
        self.reconnect(print_errors=True);

    def reconnect(self, print_errors=False):
        if self.mod_name == "error":
            if print_errors: print "ERROR: run_server or run_client must be called before reconnect";
        elif self.mode == "server":
            if os.name == "posix" and self.mod_name != "" and self.mod_name != False:
                self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM);
                if self.IDprefix and self.ID != 'SIM':
                    self.server_socket.bind("\0"+self.ID+self.mod_name)
                else:
                    self.server_socket.bind("\0"+self.mod_name); #null-byte required for "abstract namespace"
            else:
                if print_errors: print "Note: Using TCP/IP sockets on port ",self.win32port
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
                self.server_socket.bind(('',self.win32port));

            # listen to incoming connections (allow a backlog of 5)
            self.server_socket.listen(5);

            # Andrew Tinka hates blocking sockets
            self.server_socket.setblocking(0);
            self.connected = True;

            #start from scratch
            self.clients = [];
            if self.IDprefix:
                self.prefix_cache = {}
                config.message_types.append('IDPREFIX')

        elif self.mode == "client":
            try:
                # can we use unix sockets?
                if os.name == "posix" and self.mod_name != "" and self.mod_name != False:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM);
                    if self.IDprefix and self.ID != 'SIM':
                        if sock.connect_ex("\0"+self.ID+self.mod_name) != 0: 
                            if sock.connect_ex("\0"+self.mod_name) != 0:
                                if print_errors: print "WARNING: couldn't connect to ",self.mod_name
                                self.connected = False
                                return
                    else:
                        if sock.connect_ex("\0"+self.mod_name) != 0:
                            if print_errors : print "WARNING: couldn't connect to ",self.mod_name
                            self.connected = False
                            return
                else:
                    if print_errors : print "Connecting to "+self.remote_host+":",self.win32port
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
                    sock.connect((self.remote_host,self.win32port));
                    
                
                sock.setblocking(0);
                client = self.IPCClient()
                client.sock = sock;
                client.address = self.mod_name;
                client.rxbuffer = '';
                client.txbuffer = '';
                client.ip = sock.getpeername();
                client.bad_headers = 0;
                self.clients = []; # just in case we didn't disconnect from before
                self.clients.append(client);
                self.connected = True;
                
                if self.IDprefix:
                    self.prefix_cache = {}
                    config.message_types.append('IDPREFIX')
                    self.send('IDPREFIX','')
                                        
            except Exception, msg:
                if print_errors : print "WARNING: Could not start client for ",self.mod_name,":",msg
                self.connected = False;


    def tick(self):
        retvals = []

        # Try to get new clients
        if self.mode == "server" :
          try :
              new_conn, addr = self.server_socket.accept()
              new_conn.setblocking(0);
              #print "Note: Client at ",addr," connected"
              # socket object, address, bytes waiting for,buffer
              client = self.IPCClient()
              client.sock = new_conn;
              client.address = addr;
              client.rxbuffer = '';
              client.txbuffer = '';
              client.ip = new_conn.getpeername();
              client.bad_headers = 0;
              self.clients.append(client);
          except socket.error, (errno, msg) :
              if errno != 10035 and errno != 11 : # Oh shiiiii server socket died (otherwise its just a "non-block" error)
                print "ERROR: Server socket gave problem "+msg
                self.connected = False;

        if self.connected:
            for client in self.clients[:]:
                try :
                    str = client.sock.recv(4096);
                    #print "Got:",str, "-",len(str)
                    if not str: # probably disconnected or something
                        if self.mode == "client" : self.connected = False;
                        try: # try to disconnect
                            #print "Note: ",client.address," disconnected.";
                            client.sock.close();
                        except socket.error:pass
                        finally:
                            self.clients.remove(client);
                    else:
                        client.rxbuffer += str
                except socket.error, (errno, msg) :
                    if errno != 10035 and errno != 11 : # not just a "blocking socket" problem. remove socket then
                        if self.mode == "client" : self.connected = False
                        try: # try to disconnect
                            #print "Note: Socket error:",msg,". Doing damage control."
                            client.sock.close()
                        except socket.error:pass
                        finally:
                            if client in self.clients:
                                self.clients.remove(client)
                            if self.mode == "client":
                                self.connected = False
                            
                
                idx = client.rxbuffer.find('\n');
                #print "Got "+str+" from ",client.address," ",client.rxbuffer
                while idx != -1:
                    #print "Trying to parse ",client.rxbuffer[0:idx]
                    idxc = client.rxbuffer.find(':');
                    if idx <= idxc or idxc == -1:
                        print "ERROR: Malformed header ",client.rxbuffer[0:idx]
                        client.bad_headers += 1;
                        client.rxbuffer = client.rxbuffer[idx+1:len(client.rxbuffer)] # ditch it
                    else:
                        try:
                            if self.IDprefix:
                                client.IDprefix = client.rxbuffer[0:idxc];
                                if not self.prefix_cache.has_key(client.IDprefix):
                                    self.prefix_cache[client.IDprefix] = [client];
                                elif client not in self.prefix_cache[client.IDprefix]:
                                    self.prefix_cache[client.IDprefix].append(client);
                                    
                                idxc2 = client.rxbuffer.find(':',idxc+1);
                                type = client.rxbuffer[idxc+1:idxc2]
                                length = int(client.rxbuffer[idxc2+1:idx])+idx+1;
                            else:
                                type = client.rxbuffer[0:idxc]
                                length = int(client.rxbuffer[idxc+1:idx])+idx+1;
                            if len(client.rxbuffer) >= length:
                                msg = client.rxbuffer[idx+1:length]
                                client.rxbuffer = client.rxbuffer[length:len(client.rxbuffer)]
                                #print "Recieved msg of type "+type+":",msg," from ",client.address
                                if type == 'IDPREFIX':
                                    pass
                                elif type in config.message_types:
                                    retvals.append((type,msg,client));
                                    client.bad_headers = 0;
                                else:
                                    print "ERROR: Unknown message type "+type
                            else : # too long, wait for next round
                                break;
                        except ValueError, msg:
                            print "ERROR: Malformed header ",client.rxbuffer[0:idx]," ",msg
                            client.bad_headers += 1;
                            client.rxbuffer = client.rxbuffer[idx+1:len(client.rxbuffer)] # ditch it
                    
                    #next iteration
                    idx = client.rxbuffer.find('\n');
                
                if client.bad_headers > BAD_HEADER_TOLERANCE:
                    try: # try to disconnect
                        print "Note: Too many bad headers from ",client.sock," disconnecting."
                        client.sock.close()
                    except socket.error:pass
                    finally:
                        if client in self.clients:
                            self.clients.remove(client)
                        if self.mode == "client":
                            self.connected = False
                
                if len(client.txbuffer) > 0:
                    # print "Trying to send to ",client.ip
                    try:
                        sent = client.sock.send(client.txbuffer); 
                        client.txbuffer = client.txbuffer[sent:len(client.txbuffer)];
                    except socket.error, (errno, msg) :
                        if errno != 10035 and errno != 11 : # not just a "blocking socket" problem. remove socket then
                            if self.mode == "client" : connected = False
                            try: # try to disconnect
                                print "Note: Socket error:",msg,". Doing damage control."
                                client.sock.close()
                            except socket.error:pass
                            finally:
                                if client in self.clients:
                                    self.clients.remove(client)
                                if self.mode == "client":
                                    self.connected = False
                                

        
        return retvals
 
    def waitForRecv(self, timeout=1):
        curtime = time.time()
        while ( time.time() - curtime < timeout ):
            msgs = self.tick();
            if ( len(msgs) > 0 ): return msgs;
            time.sleep(0.01);
        
        return [];

    def waitForSend(self, timeout=1):
        if self.mode=="client":
            if self.connected:
                curtime = time.time()
                while ( time.time() - curtime < timeout ):
                    self.tick();
                    if ( len(self.clients[0].txbuffer) == 0 ) : return True
                    time.sleep(0.01);
                return False
            else:
                print "WARNING: Tried to wait for send while not connected"
                return False
        else:
            print "ERROR: Wait for send can only be done in client mode"
    
    # used for "waitForSend"-esque loops
    def issending(self):
        if self.mode=="client":
            return len(self.clients[0].txbuffer) > 0;
        else:
            print "ERROR: issending() only valid for client mode!"
    
    
    def clientConnected(self, client):
        return client in self.clients and self.connected;
    
    def sendTo(self, type, msg, client):
        if self.mode!="client":
            if client in self.clients and self.connected:
                if self.IDprefix:
                    client.txbuffer += self.ID + ':'
                    
                packed = type + ":%d" % (len(msg)) +'\n'
                client.txbuffer = client.txbuffer + packed + msg
            else:
                print "ERROR: Tried to send to non-existent socket or main socket closed"
        else:
            print "ERROR: sendTo() should only be used in server mode!"
            
    def sendToID(self, type, msg, ID):
        if self.mode!='client' and self.IDprefix:
            if self.prefix_cache.has_key(ID):
                sendSomething=False
                for client in self.prefix_cache[ID][:]:
                    if client in self.prefix_cache[ID] and self.connected:
                        self.sendTo(type, msg, client)
                        sendSomething = True
                    else:
                        self.prefix_cache[ID].remove(client)
                        
                if not sendSomething:
                    print "WARNING: No clients left for ID "+ID
                    del self.prefix_cache[ID]
            else:
                print "WARNING: Tried to send to non-existent ID"
        else:
            print "ERROR: sendToID() should only be used in server & IDprefix mode"
    
    def broadcast(self, type, msg):
        for client in self.clients:
            self.sendTo(type,msg,client)
    
    def send(self, type, msg):
        if self.mode=="client":
            #print "Zomg ",self.clients
            if self.connected:
                if self.IDprefix:
                    self.clients[0].txbuffer += self.ID + ':'
                    
                packed = type + ":%d" % (len(msg)) +'\n' 
                self.clients[0].txbuffer = self.clients[0].txbuffer + packed + msg
            else:
                print "WARNING: Tried to send when not connected"
        else:
            print "ERROR: Send can only be done in client mode, use sendTo or broadcast for server mode"
        
    def close(self):
        for client in self.clients:
            client.sock.close();
        if self.mode == "server": self.server_socket.close();
