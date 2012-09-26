#!/usr/bin/python
# -*- coding: utf-8 -*-

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
    
    insert [--pretend] [--from <from time>] [--to <to time>] [--type <GHMM>] <source name> <source id> <state file>
    insert [--pretend] [--from <from time>] [--to <to time>] [--type <GHMM>] <plugload name> <state file>
        Inserts a state file into the device database.
        --pretend : Don't actually do the insert, just say what's going to happen.
        --type : GHMM - input file format is a CSV with lines "states, counts, mean, variance"
        
    genstate <output state file> <reverse mapping file> [--plug <plugload name>] [--plug <plugload name>] [<source name> <source id>]
        Generate aggregate state file given plugload names and/or by looking it up via source name and source id
        
"""
    sys.exit(0);
    
op = sys.argv.pop(0)

if (op == 'list'):
    pass
elif (op == 'insert'):
    
    fromtime = None
    totime = None
    dtype = "GHMM"
    
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
            
    ret,vals,sys.argv = utils.check_arg(sys.argv,'--type',1)
    if ret:
        dtype = vals[0]

    pretend,j,sys.argv = utils.check_arg(sys.argv,'--pretend')
    
    if ( len(sys.argv) == 3 ):
        import devicedb,postgresops
        devicedb.connect();
        
        postgresops.check_evil(sys.argv[0])
        postgresops.check_evil(sys.argv[1])
        
        device_rows = devicedb.get_devices(where="source_name='%s' and '%s'=any(source_ids)"%(sys.argv[0],sys.argv[1]),limit=1)
        if ( len(device_rows) == 0 ):
            print "Cannot find device belonging to this source name/id pair"
            sys.exit(1);
        
        dev = device_rows[0]
        chan_index = dev.source_ids.index(sys.argv[1])
        print "Found device: "+dev.IDstr+" channel %d"%chan_index
        
        plugload_row = devicedb.get_devicemetas(where="key='PLUGLOAD%d'and %d=any(devices)"%(chan_index,dev.ID), limit=1)
        if( len(plugload_row)==0):
            print "Cannot find plugload metadata for this device";
            sys.exit(1);
            
        plugload_row = devicedb.get_devicemetas(where="id=%d"%plugload_row[0].parent,limit=1);
        
        plugload_name = plugload_row[0].value
        plugload_id = plugload_row[0].ID
        state_fname = sys.argv[2]
        print "Found plugload metadata: ",plugload_name
        
    elif ( len(sys.argv) == 2 ):
        plugload_name = sys.argv[0];
        state_fname = sys.argv[1];
        
        postgresops.check_evil(plugload_name);
        plugload_row = devicedb.get_devicemetas(where="key='PLUGLOAD' and value='%s'"%plugload_name,limit=1);
        if ( len(plugload_row)==0 ):
            print "Cannot find plugload metadata for "+plugload_name
            sys.exit(1)
            
        plugload_id = plugload_row[0].ID
    else:
        print "Not enough (or too many ) input arguments";
        sys.exit(1);
    
    if dtype=="GHMM":
        data = utils.readcsv(state_fname);
        if ( len(data) == 0 ):
            print "No data in file";
            sys.exit(1);
        elif len(data[0]) != 4:
            print "GHMM data file must be CSV with format \"state_no,counts,mean,variance\""
            sys.exit(1);
        
        print "Read %d states"%len(data);
        
        if not pretend:
            import learningdb
            learningdb.connect()
            learningdb.initdb();
            
            learningdb.insertHMMGaussianEmissions(plugload_id,fromtime,totime,[i[0] for i in data],[i[1] for i in data],[i[2] for i in data],[i[3] for i in data]);
    else:
        print "Invalid data type "+dtype
        sys.exit(1)
    
elif (op == 'genstate'):
    import learningdb, devicedb, postgresops
    learningdb.connect();
    
    plugnames = []
    while True:
        ret,vals,sys.argv = utils.check_arg(sys.argv,'--plug',1);
        if not ret:
            break;
            
        plugnames.append(vals[0])
    
    plugids = []
    fail = False
    for pn in plugnames:
        postgresops.check_evil(pn)
        met = devicedb.get_devicemetas(where="key='PLUGLOAD' and value='%s'"%(pn),limit=1);
        if ( len(met) == 0 ):
            print "Couldn't find plugload metadata for "+pn
            fail = True
            continue;
            
        plugids.append(met[0].ID);
    
    if fail: sys.exit(1);
    
    if ( len(sys.argv) != 2 ):
        print "Incorrect number of arguments";
        sys.exit(1);
    
    if ( len(plugids) == 0 ):
        print "No plugloads generated/given. Cannot proceed";
        sys.exit(1);
    
    state_fname = sys.argv.pop(0)
    rmap_fname  = sys.argv.pop(0)
    
    states_list = []
    for plid in plugids:
        entries = learningdb.getHMMGaussianEmissions(plid);
        states_list.append(learningdb.computeGlobalHMMGaussianParameters(entries));
    
    nStates = 1;
    for i in range(len(plugids)):
        print "%s : %d states"%(plugnames[i],len(states_list[i]))
        nStates *= len(states_list[i])
    print "Total States: %d"%nStates
    
    mfid = open(rmap_fname,"w");
    mfid.write("# Reverse state-mapping file\n");
    mfid.write("# state_no,"+','.join(plugnames)+'\n');
    sfid = open(state_fname,"w");
    sfid.write("# State file\n");
    sfid.write("# state_no,count,mean,variance\n");
    for s in range(nStates):
        modulus = 1;
        mfid.write('%d,'%s);
        cnt_acc = 0;
        mean_acc = 0.;
        var_acc = 0.;
        for i in range(len(plugids)):
            div = modulus;
            modulus *= len(states_list[i]);
            plstate = ( s % modulus ) / div;
            st = states_list[i][plstate]
            cnt_acc += st.counts;
            mean_acc += st.counts * st.mean;
            var_acc += st.counts * st.variance;
            
            mfid.write('%d'%plstate);
            if ( i != len(plugids)-1):
                mfid.write(',');
                
        mean_acc /= cnt_acc;
        var_acc /= cnt_acc;
        sfid.write("%d,%d,%.15e,%.15e\n"%(s,cnt_acc,mean_acc,var_acc));
        mfid.write('\n');
        
    mfid.close();
    sfid.close();