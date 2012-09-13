#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys,os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from mod_flow import flow_processor
from datetime import datetime, timedelta

sys.argv = sys.argv[1:]

if ( len(sys.argv) == 0):
    print """
Usage: run_flow.py [list | run]
    
    list : List available flows to run
    
    run <flow name> [--from <from time>] [--to <to time>] [--pretend] [--nocache] [--local] [--param name=value] [<source name> <device identifier>] 
        Run the given flow.  Optional time interval, default is past day.
        Optional source name and device identifier, default is all known devices.
        --pretend is for testing, doesn't actually add the tasks to the task manager
        --nocache redoes all of the steps instead of looking for cached steps
        --local makes no connections to the postgres database and manually runs the tasks, dumping the output in the current directory
            you must specify sourcename and device identifier
"""
elif (sys.argv[0] == 'list'):
    for file in os.listdir(config.map['global']['flow_dir']):
        if ( file.endswith('.flow') ):
            name = file[file.find('/')+1:-5]
            print "Flow name: "+name
            fmap = config.read_struct(config.map['global']['flow_dir']+'/'+file);
            print "\tSource type(s): ["+','.join(fmap['source_types'])+"]"
            print "\tTasks:\n\t\t"+'\n\t\t'.join(fmap['tasks'])
            print ""    
elif (sys.argv[0] == 'run'):
    fromtime = datetime.now() - timedelta(weeks=1)
    totime = datetime.now()
    
    ret,vals,sys.argv = utils.check_arg(sys.argv,'--from',1)
    if ret:
        try:
            fromtime = utils.str_to_date(vals[0])
        except ValueError, msg:
            print "Bad from time: "+str(msg)
    
    ret,vals,sys.argv = utils.check_arg(sys.argv,'--to',1)
    if ret:
        try:
            totime = utils.str_to_date(vals[0])
        except ValueError, msg:
            print "Bad to time: "+str(msg)

    
    pretend,j,sys.argv = utils.check_arg(sys.argv,'--pretend')
    local,j,sys.argv = utils.check_arg(sys.argv,'--local')
    nocache,j,sys.argv = utils.check_arg(sys.argv,'--nocache')
    
    params = {}
    while True:
        ret,vals,sys.argv = utils.check_arg(sys.argv,'--param',1)
        if not ret: break
        name,value = vals[0].split('=')
        params[name] = value;
    
    flow = flow_processor.read_flow_file(sys.argv[1])
    if ( flow ):
        if ( len(sys.argv) > 2 ):
            flow.run( fromtime, totime, sys.argv[2], sys.argv[3], pretend = pretend, local=local,use_cache= not nocache, params=params )
        else:
            flow.run( fromtime, totime, pretend = pretend, use_cache= not nocache, local=local,params=params )
    else:
        print "couldn't load the flow definition file"
else:
    print "Unknown command "+sys.argv[0]   
    