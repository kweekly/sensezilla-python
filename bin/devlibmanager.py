#!/usr/bin/python

import sys,os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime, timedelta

sys.argv = sys.argv[1:]

if ( len(sys.argv) == 0):
    print """
Usage: devlibmanager.py [insert | list]
    list
        Lists devices we know about and their current parameters
    
    insert [--pretend] [--from <from time>] [--to <to time>] <source name> <source id> <state file>
    insert [--pretend] [--from <from time>] [--to <to time>] <plugload name> <state file>
        Inserts a state file into the device database.
        --pretend : Don't actually do the insert, just say what's going to happen.
        
    genstate <output file> <plugload name1> <plugload name2> ... <plugload name3>
        Generate a state file using the plugload names
"""
op = sys.argv.pop(0)

if (op == 'list'):
    pass
elif (op == 'insert'):
    
    fromtime = None
    totime = None
    
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
    
    if ( len(sys.argv) == 3 ):
        import devicedb,postgresops
        devicedb.connect();
        
        
    elif ( len(sys.argv) == 2 ):
        plugload_name = sys.argv[0];
        state_fname = sys.argv[1];
    else:
        print "Not enough (or too many ) input arguments";
        sys.exit(1);
    
    
elif (op == 'genstate'):
    pass