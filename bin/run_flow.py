#!/usr/bin/python

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
    
    run <flow name> [--from <from time>] [--to <to time>] [--pretend] [<source name> <device identifier>] 
        Run the given flow.  Optional time interval, default is past day.
        Optional source name and device identifier, default is all known devices.
        Pretend is for testing, doesn't actually add the tasks to the task manager
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
    
    try:
        i = sys.argv.index('--from')
        try:
            fromtime = utils.str_to_date(sys.argv[i+1])
        except ValueError, msg:
            print "Bad from time: "+str(msg)
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:pass
    
    try:
        i = sys.argv.index('--to')
        try:
            totime = utils.str_to_date(sys.argv[i+1])
        except ValueError, msg:
            print "Bad to time: "+str(msg)
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:pass
    
    pretend = False
    try:
        i = sys.argv.index('--pretend')
        sys.argv = sys.argv[0:i] + sys.argv[i+1:]
        pretend = True
    except ValueError:pass
    
    flow = flow_processor.read_flow_file(sys.argv[1])
    if ( flow ):
        if ( len(sys.argv) > 2 ):
            flow.run( fromtime, totime, sys.argv[2], sys.argv[3], pretend = pretend )
        else:
            flow.run( fromtime, totime, pretend = pretend )
    else:
        print "couldn't load the flow definition file"
else:
    print "Unknown command "+sys.argv[0]   
    