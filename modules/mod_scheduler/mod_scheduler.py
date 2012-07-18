# -*- coding: utf-8 -*-
import os,sys, re
import time
from datetime import datetime, timedelta
# Gen3 common modules
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import unixIPC
import scheduler_cmd_pb2
import scheduler_resp_pb2
import asyncprocess
import signal

import google.protobuf

import scheduledb

## CONFIG VARS

DB_CHECK_INTERVAL = config.map['mod_scheduler']['db_check_interval']
MAX_CHILDREN = config.map['mod_scheduler']['max_children']
MIN_CHILDREN = config.map['mod_scheduler']['min_children']
TARGET_CORES = config.map['mod_scheduler']['target_cores']

class ChildProcess:pass

def check_db():
    pass

def find_child_by_id(id):
    for child in children:
        if child.task.id == id:
            return child
    return None

def child_start_task(task):
    global children
    
    child = ChildProcess()
    children.append(child)
    child.task = task;
    try:
        child.fout = open(child.task.log_file,'a',0)
    except IOError,msg:
        child.fout = stdout
        child_write_out(child,"Couldn't open log file for writing: "+msg)
        
    try:
        child.process = asynchprocess.Popen(task.command.split(' ', 1), stdin=asyncprocess.PIPE, stderr=asyncprocess.PIPE, stdout=asyncprocess.PIPE, bufsize=1, universal_newlines=True);
        child.status = scheduledb.RUNNING
        child.start_time = datetime.now()
        scheduledb.update_task_mult(child.task,[['start_time',child.start_time]
                                                ['status',child.status]
                                                ])
    except OSError,msg:
        child_write_out(child,"Couldn't start process: "+msg)
        child.process = None;
        child_died(child,-1);
    
def child_timed_out(child):
    global children
    child_write_out(child,"Timed out.")
    child.process.terminate();
    child.task.end_time = datetime.now()
    child.status = scheduledb.ERROR_TIMEOUT       
    scheduledb.update_task_mult(child.task,[
            ['end_time',child.end_time],
            ['status',child.status]                        
    ])
    if ( child.fout != stdout ):
        child.fout.close()
    children.remove(child)

def child_write_out(child, msg):
    lines = msg.split('\n')
    for line in lines:
        print >> child.fout,line    

def child_kill(child):
    global children
    if child.status != scheduledb.RUNNING:
        print "Can't kill task %d because it isn't running"%(child.task.id)
        
    child_write_out(child,"Killed.")
    child.process.terminate();
    child.task.end_time = datetime.now()
    child.status = scheduledb.STOPPED
    scheduledb.update_task_mult(child.task,[
            ['end_time',child.end_time],
            ['status',child.status]                        
    ])
    if ( child.fout != stdout ):
        child.fout.close()
    children.remove(child)

def child_died(child, retval):
    global children
    child.task.end_time = datetime.now()
    if ( retval != 0 ): # assume error
        child.task.status = scheduledb.ERROR_CRASH
    else:
        child.task.status = scheduledb.DONE        
        
    scheduledb.update_task_mult(child.task,[
            ['end_time',child.end_time],
            ['status',child.status]                        
    ])
    if ( child.fout != stdout ):
        child.fout.close()
        
    children.remove(child)
    
def child_pause(child):
    if child.status != scheduledb.RUNNING:
        print "Can't pause task %d because it isn't running"%(child.task.id)
        
    os.kill(child.process.pid, signal.SIGSTOP)
    child.status = scheduledb.PAUSED
    scheduledb.update_task(child.task,'status',child.status)
    
def child_unpause(child):
    if child.status != scheduledb.PAUSED:
        print "Can't unpause task %d because it isn't paused"%(child.task.id)
        
    os.kill(child.process.pid, signal.SIGCONT)
    child.status = scheduledb.RUNNING
    scheduledb.update_task(child.task,'status',child.status)
    
# connect to postgres
scheduledb.connect()
if scheduledb.connected():
    scheduledb.initdb()
else:
    print "ERROR: Cannot connect to postgre database"
    sys.exit(1)

# host unix socket
unixIPC = unixIPC.UnixIPC();
unixIPC.run_server("mod_scheduler", int(config.map['mod_scheduler']['port']));

# the subprocesses
children = []

#timeouts
last_db_check = time.time()

while True:
    if ( not scheduledb.connected() ):
        scheduledb.connect()
    else:
        if ( time.time() - last_db_check > DB_CHECK_INTERVAL ):
            check_db()
            last_db_check = time.time()
        
    if ( not unixIPC.connected ):
        unixIPC.reconnect()
    else:
        msgs = unixIPC.tick()
        for type,msg,client in msgs:
            if type=='scheduler_cmd_pb2':
                scheduler_cmd_msg = scheduler_cmd_pb2.Scheduler_Cmd();
                scheduler_cmd_msg.ParseFromString(msg)
                if scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.FORCE_START:
                    task = scheduledb.get_task_by_id(scheduler_cmd_msg.task_id)
                    if ( task != None ):
                        child_start_task(task)
                    else:
                        print "Error task ID %d not found"%scheduler_cmd_msg.task_id
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.PAUSE:
                    child = find_child_by_id(scheduler_cmd_msg.task_id)
                    if ( child != None ):
                        child_pause(child)
                    else:
                        print "Error running task ID %d not found"%scheduler_cmd_msg.task_id    
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.PAUSE_ALL:
                    for child in children:
                        child_pause(child)
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.UNPAUSE:
                    child = find_child_by_id(scheduler_cmd_msg.task_id)
                    if ( child != None ):
                        child_unpause(child)
                    else:
                        print "Error running task ID %d not found"%scheduler_cmd_msg.task_id    
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.UNPAUSE_ALL:
                    for child in children:
                        child_unpause(child)
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.KILL:
                    child = find_child_by_id(scheduler_cmd_msg.task_id)
                    if ( child != None ):
                        child_kill(child)
                    else:
                        print "Error running task ID %d not found"%scheduler_cmd_msg.task_id
                elif scheduler_cmd_msg.command == scheduler_cmd_pb2.Scheduler_Cmd.KILL_ALL:
                    for child in children:
                        child_kill(child)
            else:
                print "Unknown message type "+type
    
    for child in children[:]:
        try:
            outdat = child.process.recv(1000);
            errdat = child.process.recv_err(1000);
        except OSError, msg:
            try:
                child.process.terminate();
            except OSError,msg:
                pass
            outdat = None;
            errdat = None;
        
        if outdat != None and outdat != "":
            child_write_out(child, outdat)
        if errdat != None and errdat != "":
            child_write_out(child, outdat)
        
        retval = child.process.poll() 
        if retval != None: # child died
            child_died(child, retval)
            
        if datetime.now() > child.task.start_time + timedelta(seconds=child.task.deadline_s):
            child_timed_out(child)
    
    time.sleep(0.1)
    