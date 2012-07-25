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
import psutil

import google.protobuf

import scheduledb

## CONFIG VARS

DB_CHECK_INTERVAL = float(config.map['mod_scheduler']['db_check_interval'])
MAX_CHILDREN = float(config.map['mod_scheduler']['max_children'])

CPU_TARGET = float(config.map['mod_scheduler']['cpu_target'])
CPU_MAX = float(config.map['mod_scheduler']['cpu_max'])
IO_TARGET = float(config.map['mod_scheduler']['io_target'])
IO_MAX = float(config.map['mod_scheduler']['io_max'])
MEM_TARGET = float(config.map['mod_scheduler']['mem_target'])
MEM_MAX = float(config.map['mod_scheduler']['mem_max'])

class Profile:pass

profiles = {}
for profstr in config.map['mod_scheduler']['profiles']:
    p = Profile()
    pts = profstr.split(',')
    p.name = pts[0]
    p.cpu_usage = float(pts[1])
    p.io_usage = float(pts[2])
    p.mem_usage = float(pts[3])
    profiles[p.name] = p
    
class ChildProcess:pass

def check_db():
    running_tasks = scheduledb.get_tasks(where='status = %d'%(scheduledb.RUNNING))
    # check if tasks that were "running" are dead
    for task in running_tasks[:]:
        if not psutil.pid_exists(task.pid):
            print "Error: task %d was RUNNING but pid not found! Assumed dead."
            task.status = scheduledb.ERROR_CRASH
            running_tasks.remove(task)
            scheduledb.update_task(task,'status',task.status)            
    
    tasks = scheduledb.get_tasks(where='status >= %d and status <= %d'%(scheduledb.WAITING_FOR_INPUT,scheduledb.PAUSED))
    
    # check if a task was waiting on time or another task
    #print "Checking database, found %d stalled tasks"%(len(tasks))
    for task in tasks:
        task.changed = False
        if (task.status == scheduledb.WAITING_FOR_INPUT or (task.status == scheduledb.WAITING_FOR_START and task.start_after <= datetime.now())):
            if ( len(task.prerequisites) > 0 and scheduledb.count(where=' or '.join(['id = %d'%i for i in task.prerequisites])+' and status != %d'%(scheduledb.DONE)) > 0):
                task.status = scheduledb.WAITING_FOR_INPUT
                task.changed = True
            else:
                task.status = scheduledb.WAITING_FOR_CPU
                task.changed = True
        
    # check if there is CPU available for a new task        
    curcpu = 0
    curio = 0
    curmem = 0
    
    for task in running_tasks:
        prof = profiles[task.profile_tag]
        curcpu += prof.cpu_usage
        curio += prof.io_usage
        curmem += prof.mem_usage
    
    #print "Current cpu=%.2f%% io=%.2fMBps mem=%.2fMB"%(curcpu*100.0,curio,curmem)
    tasks_to_start = []
    if ( len(running_tasks) < MAX_CHILDREN):
        if (curcpu < CPU_TARGET):
            for task in tasks:
                prof = profiles[task.profile_tag]
                if ( task.status == scheduledb.WAITING_FOR_CPU and prof.cpu_usage > 0 and 
                     prof.cpu_usage + curcpu <= CPU_MAX and prof.io_usage + curio <= IO_MAX and prof.mem_usage + curmem <= MEM_MAX ):
                        tasks_to_start.append(task)
                        curcpu += prof.cpu_usage
                        curmem += prof.mem_usage
                        curio += prof.io_usage
                        task.status = scheduledb.RUNNING
                        
        if (curmem < MEM_TARGET):
            for task in tasks:
                prof = profiles[task.profile_tag]
                if ( task.status == scheduledb.WAITING_FOR_CPU and prof.mem_usage > 0 and 
                     prof.cpu_usage + curcpu <= CPU_MAX and prof.io_usage + curio <= IO_MAX and prof.mem_usage + curmem <= MEM_MAX ):
                        tasks_to_start.append(task)
                        curcpu += prof.cpu_usage
                        curmem += prof.mem_usage
                        curio += prof.io_usage
                        task.status = scheduledb.RUNNING
                        
        if (curio < IO_TARGET):
            for task in tasks:
                prof = profiles[task.profile_tag]
                if ( task.status == scheduledb.WAITING_FOR_CPU and prof.io_usage > 0 and 
                     prof.cpu_usage + curcpu <= CPU_MAX and prof.io_usage + curio <= IO_MAX and prof.mem_usage + curmem <= MEM_MAX ):
                        tasks_to_start.append(task)
                        curcpu += prof.cpu_usage
                        curmem += prof.mem_usage
                        curio += prof.io_usage
                        task.status = scheduledb.RUNNING
                       
    # start the tasks we should start
    for task in tasks_to_start:
        child_start_task(task)
     
    # update the database
    for task in tasks:
        if task.changed:
            scheduledb.update_task(task,'status',task.status)
        

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
        child.fout = sys.stdout
        child_write_out(child,"Couldn't open log file for writing: "+str(msg))
        
    try:
        child.process = asyncprocess.Popen(task.command.split(' '), stdin=asyncprocess.PIPE, stderr=asyncprocess.PIPE, stdout=asyncprocess.PIPE, bufsize=1, universal_newlines=True);
        child.task.pid = child.process.pid
        child.task.status = scheduledb.RUNNING
        child.start_time = datetime.now()
        scheduledb.update_task_mult(child.task,[['start_time',child.start_time],
                                                ['status',child.task.status],
                                                ['pid',child.task.pid]
                                                ])
    except OSError,msg:
        child_write_out(child,"Couldn't start process: "+str(msg))
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

statexpr = re.compile(r"^PROGRESS STEP (?P<stepd>\d+) OF (?P<stept>\d+) \"(?P<stepn>.+?)\" (?P<prog>.*?) DONE$")

def child_write_out(child, msg):
    msg = msg.rstrip();
    m = statexpr.match(msg)
    if m :
        child.task.progress_steps_done = m.group('stepd')
        child.task.progress_steps_total= m.group('stept')
        child.task.step_description    = m.group('stepn')
        child.task.step_progress_str   = m.group('prog')
        
        scheduledb.update_task_mult(child.task,[
             ['progress_steps_done', child.task.progress_steps_done],
             ['progress_steps_total', child.task.progress_steps_total],
             ['step_description', child.task.step_description],
             ['step_progress_str',child.task.step_progress_str]
        ])
        
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
            ['end_time',child.task.end_time],
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
            ['end_time',child.task.end_time],
            ['status',child.task.status]                        
    ])
    if ( child.fout != sys.stdout ):
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
            child_write_out(child, errdat)
        
        retval = child.process.poll() 
        if retval != None: # child died
            child_died(child, retval)
            
        if datetime.now() > child.task.start_time + timedelta(seconds=child.task.deadline_s):
            child_timed_out(child)
    
    time.sleep(0.1)
    