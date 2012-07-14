# -*- coding: utf-8 -*-
import asyncprocess
import os, sys, re, os.path, time


if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Please set it"
    sys.exit(1);
    
sys.path.insert(0, os.environ['SENSEZILLA_DIR'] + "/includes");


class ExecProcess:pass

#Stevens, W. Richard. I{Unix Network Programming} (Addison-Wesley, 1990).
def daemonize():
    if os.name != 'posix':
        print 'Daemon is only supported on Posix-compliant systems.'
        return

    try:
        # Fork once to go into the background.
        pid = os.fork()
        if pid != 0:
            # Parent. Exit using os._exit(), which doesn't fire any atexit
            # functions.
            os._exit(0)
    
        # First child. Create a new session. os.setsid() creates the session
        # and makes this (child) process the process group leader. The process
        # is guaranteed not to have a control terminal.
        os.setsid()
    
        # Fork a second child to ensure that the daemon never reacquires
        # a control terminal.
        pid = os.fork()
        if pid != 0:
            # Original child. Exit.
            os._exit(0)
            
        # This is the second child. Set the umask.
        os.umask(0)
    
        # Go to a neutral corner (i.e., the primary file system, so
        # the daemon doesn't prevent some other file system from being
        # unmounted).
        os.chdir('/')

    except OSError, e:
        print "Error daemonizing: ", e
        sys.exit(1);

def print_log(msg):
    print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + msg

def find_proc(name):
    for mod in modules:
        if mod.name == name:
            return mod;
    return None    
    
#############################################################################################
################################# START OF PROGRAM ##########################################
#############################################################################################
#############################################################################################
daemonize();

import config
import unixIPC
import exec_cmd_pb2
import exec_resp_pb2
import google.protobuf


config.force_load();
# start IPC server
unixIPC = unixIPC.UnixIPC();
unixIPC.run_server("mod_exec", int(config.map['mod_exec']['port']));

modules = []
for mod in config.map['mod_exec']['modules']:
    try:
        (startup_state, delay, name, cmd) = mod.split(',');
    except ValueError, e:
        print "ERROR: Invalid mod_exec line: \"" + mod + "\""
        continue;

    proc = ExecProcess()
    proc.cmd = cmd;
    proc.delay_start = int(delay);
    proc.countdown = 0
    proc.name = name
    
    if startup_state == 'START': 
        proc.running = True
        proc.should_run = True
        print "mod_exec: starting \"" + proc.cmd + "\""
        try :
            # redirect to pipe, line-buffered, universal newlines
            proc.process = asyncprocess.Popen(proc.cmd.split(' ', 1), stdin=asyncprocess.PIPE, stderr=asyncprocess.PIPE, stdout=asyncprocess.PIPE, bufsize=1, universal_newlines=True); 
            time.sleep(1)
            #no redirection
            #proc.process = asyncprocess.Popen(proc.cmd.split(' ',1), bufsize=1, universal_newlines=True); 

        except OSError, msg:
            print "ERROR: mod_exec cannot start \"" + proc.cmd + "\":", msg
            proc.running = False
    elif startup_state == 'NOSTART':
        proc.running = False
        proc.should_run = False
    else:
        print "ERROR: must specify startup state for " + mod
        sys.exit(1);
 
    modules.append(proc);

#unbuffered output to logfile
if (config.check_key('mod_exec', 'logfile')):
    logfile = open(config.map['mod_exec']['logfile'], 'a', 0)
else:
    logfile = sys.stdout
    
print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "*** mod_exec started ***"

last_time = time.time();
while 1:
    curtime = time.time();
    dt = curtime - last_time;
    last_time = curtime;
    for mod in modules:
        if mod.running == True: # process still running... communicate ( could have died, but we still want to capture output)
            try:
                outdat = mod.process.recv(1000);
                #print outdat
                errdat = mod.process.recv_err(1000);
            except OSError, msg:
                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot read \"" + mod.cmd + "\":", msg
                mod.should_run = False; # force it to be killed
                outdat = None;
                errdat = None;
            #print errdat
            if outdat != None and outdat != "":
                lines = outdat.split('\n') # works b/c of universal newlines
                for line in lines:
                    if line != "":
                        print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), mod.name) + line
            if errdat != None and errdat != "":
                lines = errdat.split('\n') # works b/c of universal newlines
                for line in lines:
                    if line != "":
                        print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), mod.name.upper()) + line
            
        if mod.running == True and mod.process.poll() != None:
           print_log("child died  : \"" + mod.cmd + "\"")
           mod.running = False
           mod.countdown = mod.delay_start;
        elif mod.running == True and mod.should_run == False:
            print_log("killing child : \"" + mod.cmd + "\"");
            try:
                mod.process.terminate();
            except OSError, msg:
                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot kill \"" + mod.cmd + "\":", msg
                mod.running = False
        elif mod.should_run == True and mod.running == False and mod.countdown <= 0:
            print_log("restarting child \"" + mod.cmd + "\"")
            try :
                mod.process = asyncprocess.Popen(mod.cmd.split(' ', 1), stdin=asyncprocess.PIPE, stderr=asyncprocess.PIPE, stdout=asyncprocess.PIPE, bufsize=1, universal_newlines=True); 
                mod.running = True;
            except OSError, msg:
                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot start \"" + mod.cmd + "\":", msg
                mod.countdown = mod.delay_start;
        elif mod.running == False and mod.countdown > 0:
            mod.countdown -= dt
    
    if not unixIPC.connected:
        unixIPC.reconnect();
    else:
        msgs = unixIPC.tick();
        for (type, msg, client) in msgs:
            if type == 'exec_cmd_pb2':
                exec_cmd_msg = exec_cmd_pb2.Exec_Cmd();
                try:
                    exec_cmd_msg.ParseFromString(msg);
                    if exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.KILL:
                        print_log("Told to kill [all]");
                        for mod in modules:
                            try:
                                mod.process.terminate();
                            except OSError, msg:
                                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot kill \"" + mod.cmd + "\":", msg
                                mod.running = False
                                
                        sys.exit(0);
                    elif exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.STOP:
                        print_log("Told to stop " + exec_cmd_msg.name);
                        mod = find_proc(exec_cmd_msg.name);
                        if (mod != None):
                            mod.should_run = False;
                            try:
                                mod.process.terminate();
                            except OSError, msg:
                                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot kill \"" + mod.cmd + "\":", msg
                                mod.running = False
                            
                        else:
                            print_log("Process " + exec_cmd_msg.name + " not found.");
                    elif exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.START:
                        print_log("Told to start " + exec_cmd_msg.name);
                        mod = find_proc(exec_cmd_msg.name);
                        if (mod != None):
                            mod.should_run = True;
                            mod.countdown = 0;
                        else:
                            print_log("Process " + exec_cmd_msg.name + " not found.");                    
                    elif exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.RESTART:
                        print_log("Told to restart " + exec_cmd_msg.name);
                        mod = find_proc(exec_cmd_msg.name);
                        if (mod != None):
                            mod.should_run = True;
                            mod.countdown = 0;
                            try:
                                mod.process.terminate();
                            except OSError, msg:
                                print >> logfile, "%-24s : [%-10s] : " % (time.asctime(), "mod_exec") + "ERROR: mod_exec cannot kill \"" + mod.cmd + "\":", msg
                                mod.running = False
                        else:
                            print_log("Process " + exec_cmd_msg.name + " not found.");
                    elif exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.LIST:
                        exec_resp_msg = exec_resp_pb2.Exec_Resp();
                        exec_resp_msg.type = exec_resp_pb2.Exec_Resp.STATE;
                        for mod in modules:
                            proc = exec_resp_msg.processes.add();
                            proc.name = mod.name;
                            if not mod.running and not mod.should_run:
                                proc.state = exec_resp_pb2.Exec_Resp.STOPPED
                            elif not mod.running and mod.should_run:
                                proc.state = exec_resp_pb2.Exec_Resp.RESTARTING
                            elif mod.running:
                                proc.state = exec_resp_pb2.Exec_Resp.RUNNING
                            
                        unixIPC.sendTo('exec_resp_pb2', exec_resp_msg.SerializeToString(), client);
                    elif exec_cmd_msg.command == exec_cmd_pb2.Exec_Cmd.STATE:
                        exec_resp_msg = exec_resp_pb2.Exec_Resp();
                        exec_resp_msg.type = exec_resp_pb2.Exec_Resp.STATE;
                        mod = find_proc(exec_cmd_msg.name);
                        if mod != None:
                            proc = exec_resp_msg.processes.add();
                            proc.name = mod.name;
                            if not mod.running and not mod.should_run:
                                proc.state = exec_resp_pb2.Exec_Resp.STOPPED
                            elif not mod.running and mod.should_run:
                                proc.state = exec_resp_pb2.Exec_Resp.RESTARTING
                            elif mod.running:
                                proc.state = exec_resp_pb2.Exec_Resp.RUNNING
                            
                            unixIPC.sendTo('exec_resp_pb2', exec_resp_msg.SerializeToString(), client);                        
                        else:
                            print_log("Process " + exec_cmd_msg.name + " not found.");
                    else:
                        print_log("Invalid IPC command given");
                except google.protobuf.message.DecodeError, msg:
                    print_log("Malformed " + type + " message " + msg);
                
            else:
                print_log("Invalid message received: " + type);
    time.sleep(0.1);
