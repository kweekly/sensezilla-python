
import config
import utils

import serial
from xbee import XBee, ZigBee
import time,os,sys

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
    
    SERIAL_PORT = '/dev/ttyO1'
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


def init_xbee(s,x):
    global ser, xbee
    ser = s;
    xbee = x;
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
        
        if cmd == 'NK' or cmd == 'KY':
            xbee.send('at',command=atcmd,parameter=sstr)
        else:
            if verify_at(cmd,sstr):
                something_changed = True

    if something_changed:
        xbee.send('at',command='WR')
