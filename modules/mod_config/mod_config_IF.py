# -*- coding: utf-8 -*-
## NO ONE MUST USE THIS PORT!!!!! ##
CONFIG_PORT = 10001;

# -*- coding: utf-8 -*-
# interface module for mod_config
# Interface imported by:
#    from mod_config import mod_config_IF
# Kevin Weekly

import sys, os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import unixIPC
import config_cmd_pb2
import config_resp_pb2

blocking_mode = True
ipc = unixIPC.UnixIPC()

def connect(block_sends=True):
    global blocking_mode
    blocking_mode = block_sends
    ipc.run_client("mod_config", CONFIG_PORT);

def tick():
    ipc.tick()

def flush(): 
    ipc.waitForSend()

def reconnect():
    ipc.reconnect()
    
def disconnect():
    ipc.close()

def connected():
    return ipc.connected;

def getVal(mod_name, key):
    config_cmd_msg = config_cmd_pb2.Config_Cmd();
    config_cmd_msg.cmd = config_cmd_pb2.Config_Cmd.GET;
    config_cmd_msg.mod_name = mod_name;
    config_cmd_msg.key = key;
    msg = config_cmd_msg.SerializeToString()
    ipc.send("config_cmd_pb2",msg);
    
    msgs = ipc.waitForRecv();
    if len(msgs) == 0:
        print "ERROR: IPC timeout to mod_config during getVal()";
        return None;
    
    # Bad idea ahead. Works for mod_gpio b/c it only sends solicited gpio_resp messages
    if len(msgs) > 1:
        print "Note: Uh-oh, I ate extra messages: ",msgs[1:len(msgs)]
    (type, msg, client) = msgs[0];
    config_resp_msg = config_resp_pb2.Config_Resp()
    
    try:
        config_resp_msg.ParseFromString(msg);
    except google.protobuf.message.DecodeError:
        print "Error parsing config_resp_msg"  
    
    if ( config_resp_msg.error != "OK" ):
        print "ERROR: from mod_config:",config_resp_msg.error
        return None
    
    if config_resp_msg.mod_name == mod_name and config_resp_msg.key == key:
        val = config_resp_msg.val;
        if(val[0] == '\n'):
            val = val[1:].split('\n');
        return val;
    else:
        print "ERROR: I asked for %s.%s and mod_config returned %s.%s"%(mod_name,key,config_resp_msg.mod_name,config_resp_msg.key);
    
    return None;
    
def setVal(mod_name, key, val):
    config_cmd_msg = config_cmd_pb2.Config_Cmd();
    config_cmd_msg.cmd = config_cmd_pb2.Config_Cmd.SET;
    config_cmd_msg.mod_name = mod_name;
    config_cmd_msg.key = key;
    if (type(val) is list):
        val = "\n"+"\n".join(val);
    config_cmd_msg.val = val;
    msg = config_cmd_msg.SerializeToString()
    ipc.send("config_cmd_pb2",msg);
    flush();
    
def setVals(mod_names, keys, vals):
    config_cmd_msg = config_cmd_pb2.Config_Cmd();
    config_cmd_msg.cmd = config_cmd_pb2.Config_Cmd.SET_ALL;
    for idx in range(0,len(mod_names)):
        config_cmd_msg.mod_names.append(mod_names[idx])
        config_cmd_msg.keys.append(keys[idx]);
        val = vals[idx];
        if (type(val) is list):
            val = "\n"+"\n".join(val);
        config_cmd_msg.vals.append(val);
        
    msg = config_cmd_msg.SerializeToString()
    ipc.send("config_cmd_pb2",msg);
    flush();    
    
def getAll():
    config_cmd_msg = config_cmd_pb2.Config_Cmd();
    config_cmd_msg.cmd = config_cmd_pb2.Config_Cmd.GET_ALL;
    msg = config_cmd_msg.SerializeToString()
    ipc.send("config_cmd_pb2",msg);
    
    msgs = ipc.waitForRecv();
    if len(msgs) == 0:
        print "ERROR: IPC timeout to mod_config during getVal()";
        return None;
    
    # Bad idea ahead. Works for mod_gpio b/c it only sends solicited gpio_resp messages
    if len(msgs) > 1:
        print "Note: Uh-oh, I ate extra messages: ",msgs[1:len(msgs)]
    (type, msg, client) = msgs[0];
    config_resp_msg = config_resp_pb2.Config_Resp()
    
    try:
        config_resp_msg.ParseFromString(msg);
    except google.protobuf.message.DecodeError:
        print "Error parsing config_resp_msg"  
    
    if ( config_resp_msg.error != "OK" ):
        print "ERROR: from mod_config:",config_resp_msg.error
        return None
    
    mod_names = config_resp_msg.mod_names;
    keys = config_resp_msg.keys;
    vals = config_resp_msg.vals;
    ret = [];
    for idx in range(0,len(mod_names)):
        val = vals[idx];
        if(val[0]=='\n'):
            val = val[1:].split('\n');
        ret.append((mod_names[idx],keys[idx],val));
    
    return ret;

# if this is run on cmd line, just run some tests
  
if __name__ == "__main__":
    if 'GEN3DIR' not in os.environ:
        print "Note: GEN3DIR not provided. Assuming ../../"
        os.environ['GEN3DIR'] = "../.."

    sys.path.insert(0,os.environ['GEN3DIR']+"/gen3includes");
    connect();
    print getVal('global','root_dir');
    print config.map['centerline']['policy_set']
    setVal('global','root_dir','asdf');
    print getVal('global','root_dir');
    setVals(['a','b','c'],['d','e','f'],['zxcv','sadf','qwer']);
    vals = getAll();
    for (mod,key,val) in vals:
        print "%s.%s : %s"%(mod,key,val);
    disconnect();
