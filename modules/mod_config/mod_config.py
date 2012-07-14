# -*- coding: utf-8 -*-
import os,sys, re
import time
# Gen3 common modules
if 'GEN3DIR' not in os.environ:
    print "Note: GEN3DIR not provided. Assuming ../../"
    os.environ['GEN3DIR'] = "../.."

sys.path.insert(0,os.environ['GEN3DIR']+"/gen3includes");
import config
import mod_config_IF
import unixIPC

import config_cmd_pb2;
import config_resp_pb2;
import google.protobuf


    
config.force_load();

cmap = config.map;
   
    
############# START THE SERVER ############################

unixIPC = unixIPC.UnixIPC();
unixIPC.run_server("mod_config", mod_config_IF.CONFIG_PORT);

while(1):
    if not unixIPC.connected:
        unixIPC.reconnect();
    else:
        msgs = unixIPC.tick();
        for (mtype, msg, client) in msgs:
            #print "Got message of type ",type," : ",msg
            if mtype == 'config_cmd_pb2':
                config_cmd_msg = config_cmd_pb2.Config_Cmd()
                try:
                    config_cmd_msg.ParseFromString(msg)
                    if config_cmd_msg.cmd == config_cmd_pb2.Config_Cmd.SET:
                        mod_name = config_cmd_msg.mod_name;
                        key = config_cmd_msg.key;
                        val = config_cmd_msg.val;
                        
                        if ( not config.map.has_key(mod_name) ):
                            config.map[mod_name] = config.IPCMap();
                        
                        if(val[0] == '\n'):
                            val = val[1:].split('\n');
                            
                        config.map[mod_name][key] = val;
                        
                    elif config_cmd_msg.cmd == config_cmd_pb2.Config_Cmd.GET:
                        mod_name = config_cmd_msg.mod_name;
                        key = config_cmd_msg.key;
                        
                        #print "FRIEENDS!! ",mod_name,key
                        config_resp_msg = config_resp_pb2.Config_Resp();
                        config_resp_msg.type = config_resp_pb2.Config_Resp.VAL;
                        config_resp_msg.mod_name = mod_name;
                        config_resp_msg.key = key;
                        
                        if ( not config.map.has_key(mod_name) or not config.map[mod_name].has_key(key) ):
                            config_resp_msg.error = "Key not found"
                        else:
                            config_resp_msg.error = "OK"
                            val =  config.map[mod_name][key];
                            if (type(val) is list):
                                val = "\n"+"\n".join(val);
                            config_resp_msg.val = val;
 
                        unixIPC.sendTo("config_resp_pb2",config_resp_msg.SerializeToString(),client);
                        
                    elif config_cmd_msg.cmd == config_cmd_pb2.Config_Cmd.SET_ALL:
                        mod_names = config_cmd_msg.mod_names;
                        keys = config_cmd_msg.keys;
                        vals = config_cmd_msg.vals;
                        
                        for midx in range(0,len(mod_names)):
                            if ( not config.map.has_key(mod_names[midx]) ):
                                config.map[mod_names[midx]] = config.IPCMap();
                                
                            val = vals[midx];
                            if(val[0] == '\n'):
                                val = val[1:].split('\n');
                            config.map[mod_names[midx]][keys[midx]] = val;
                    
                    elif config_cmd_msg.cmd == config_cmd_pb2.Config_Cmd.GET_ALL:
                        config_resp_msg = config_resp_pb2.Config_Resp();
                        config_resp_msg.type = config_resp_pb2.Config_Resp.VALS;
                        
                        for mod_name,mod_hash in config.map.items():
                            for key,val in mod_hash.items():
                                config_resp_msg.mod_names.append(mod_name);
                                config_resp_msg.keys.append(key);
                                if (type(val) is list):
                                    val = "\n"+"\n".join(val);
                                config_resp_msg.vals.append(val);
                                
                        config_resp_msg.error = "OK"
                        unixIPC.sendTo("config_resp_pb2",config_resp_msg.SerializeToString(),client);
                        
                    elif config_cmd_msg.cmd == config_cmd_pb2.Config_Cmd.REVERT:
                        pass
                    else:
                        print "ERROR: Invalid mod_config command ",config_cmd_msg.cmd
                except google.protobuf.message.DecodeError, msg:
                    print "ERROR: Malformed ",type," message ",msg
                
            else:
                print "ERROR: mod_config does not know how to handle message type ",type
    

    
    # try not to burn through cpu
    time.sleep(0.1);