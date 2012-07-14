# -*- coding: utf-8 -*-
# interface module for mod_exec
# Interface imported by:
#    from mod_exec import mod_exec_IF
# Kevin Weekly

import sys, os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import unixIPC
import exec_cmd_pb2
import exec_resp_pb2
import google.protobuf

( RUNNING, STOPPED, RESTARTING ) = range(0,3);
state_names = ('RUNNING','STOPPED','RESTARTING');

class Process:pass

blocking_mode = True
unixIPC = unixIPC.UnixIPC()

def connect(block_sends=True):
    global blocking_mode
    blocking_mode = block_sends
    unixIPC.run_client("mod_exec", int(config.map['mod_exec']['port']));
    
def reconnect():
    unixIPC.reconnect()

def tick():
    unixIPC.tick()

def flush(): 
    unixIPC.waitForSend()

def disconnect():
    unixIPC.close()

def connected():
    return unixIPC.connected;

def kill():
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.KILL
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    if blocking_mode:
        flush()

def start(proc_name):
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.START
    exec_cmd_msg.name = proc_name
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    if blocking_mode:
        flush()

def stop(proc_name):
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.STOP
    exec_cmd_msg.name = proc_name
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    if blocking_mode:
        flush()

def restart(proc_name):
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.RESTART
    exec_cmd_msg.name = proc_name
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    if blocking_mode:
        flush()
        
def get_state(proc_name):
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.STATE
    exec_cmd_msg.name = proc_name
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    flush()
    msgs = unixIPC.waitForRecv();
    if len(msgs) == 0:
        print "ERROR: IPC timeout to mod_exec during get_state()";
    else:
        # Bad idea ahead. Works for mod_exec b/c it only sends solicited exec_resp messages
        if len(msgs) > 1:
            print "Note: Uh-oh, I ate extra messages: ",msgs[1:len(msgs)]
        (type, msg, client) = msgs[0];
        exec_resp_msg = exec_resp_pb2.Exec_Resp()
        exec_resp_msg.ParseFromString(msg);
        if exec_resp_msg.type == exec_resp_pb2.Exec_Resp.STATE:
            if exec_resp_msg.processes[0].name == proc_name:
                if exec_resp_msg.processes[0].state == exec_resp_pb2.Exec_Resp.RUNNING:
                    return RUNNING;
                elif exec_resp_msg.processes[0].state == exec_resp_pb2.Exec_Resp.STOPPED:
                    return STOPPED;
                elif exec_resp_msg.processes[0].state == exec_resp_pb2.Exec_Resp.RESTARTING:
                    return RESTARTING;
            else:
                print "ERROR: mod_exec response to a read did not return the same process name!"
        else:
            print "ERROR: Expected STATE response but got",exec_resp_msg.type

def list():
    exec_cmd_msg = exec_cmd_pb2.Exec_Cmd()
    exec_cmd_msg.command = exec_cmd_pb2.Exec_Cmd.LIST
    msg = exec_cmd_msg.SerializeToString()
    unixIPC.send("exec_cmd_pb2",msg)
    flush()
    msgs = unixIPC.waitForRecv();
    if len(msgs) == 0:
        print "ERROR: IPC timeout to mod_exec during list()";
    else:
        # Bad idea ahead. Works for mod_exec b/c it only sends solicited exec_resp messages
        if len(msgs) > 1:
            print "Note: Uh-oh, I ate extra messages: ",msgs[1:len(msgs)]
        (type, msg, client) = msgs[0];
        exec_resp_msg = exec_resp_pb2.Exec_Resp()
        
        try:
            exec_resp_msg.ParseFromString(msg);
        except google.protobuf.message.DecodeError:
            print "Error parsing exec_resp_msg"  
            
        if exec_resp_msg.type == exec_resp_pb2.Exec_Resp.STATE:
            retval = [];
            for proc in exec_resp_msg.processes:
                p = Process()
                p.name = proc.name;
                if proc.state == exec_resp_pb2.Exec_Resp.RUNNING:
                    p.state =  RUNNING;
                elif proc.state == exec_resp_pb2.Exec_Resp.STOPPED:
                    p.state = STOPPED;
                elif proc.state == exec_resp_pb2.Exec_Resp.RESTARTING:
                    p.state = RESTARTING;
                retval.append(p);
            return retval;
        else:
            print "ERROR: Expected STATE response but got",exec_resp_msg.type

            
# if this is run on cmd line, just run some tests
if __name__ == "__main__":
    connect();
    stop('mod_gpio');
    time.sleep(2);
    start('mod_gpio');
    time.sleep(2);
    restart('mod_gpio');
    time.sleep(2);
    print get_state('mod_gpio');
    time.sleep(1);
    print list();
    disconnect();
