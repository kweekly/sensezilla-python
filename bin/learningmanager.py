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
Usage: learningmanager.py [insert | list | genstate]
    list
        Lists devices we know about and their current parameters
    
    insert [--pretend] [--from <from time>] [--to <to time>] [--type <GHMM>] <source name> <source id> <state file>
    insert [--pretend] [--from <from time>] [--to <to time>] [--type <GHMM>] <plugload name> <state file>
        Inserts a state file into the device database.
        --pretend : Don't actually do the insert, just say what's going to happen.
        --type : GHMM - input file format is a CSV with lines "states, counts, mean, variance"
        
    genstate <output state file> <reverse mapping file> [--plug <plugload name>] [--plug <plugload name>] [<source name> <source id>]
        Generate aggregate state file given plugload names and/or by looking it up via source name and source id
        
    mapstate <input CSV> <reverse mapping file> <output CSV> [--rawdata <raw CSV> --invr <input value ratio>]
        Splits an input CSV timeseries (time,aggregate state no) into an output CSV timeseries (time,state1_no,state2_no...)
        Estimates the disaggregated values using rawdata file
"""
    sys.exit(0);
    
op = sys.argv.pop(0)

if (op == 'list'):
    import learningdb,devicedb
    learningdb.connect()
    print "Hidden Markov Model w/ Gaussian Emission Parameters"
    ids = learningdb.getHMMGaussianEmissionIDs()
    for id in ids:
        met = devicedb.get_devicemetas(where="id=%d"%id, limit=1)
        plname = met[0].value
        entries = learningdb.getHMMGaussianEmissions(id);
        gparm = learningdb.computeGlobalHMMGaussianParameters(entries);
        print "\tPlugload \"%s\" Total Learning Sets: %d"%(plname,len(entries))
        for g in gparm:
            print "\t\tState %-3d: N=%-7d mean=%20.10e variance=%20.10e"%(g.state_id,g.counts,g.mean,g.variance)
        print "\n";
    
    
elif (op == 'insert'):
    import devicedb,postgresops
    devicedb.connect();
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
       
        postgresops.check_evil(sys.argv[0])
        postgresops.check_evil(sys.argv[1])
        
        sname = sys.argv[0]
        sid = sys.argv[1]
        
        pl_meta,dev,pl_index = devicedb.find_plugload(sname,sid)        
        if  pl_index == None:
            print "Cannot find device belonging to this source name/id pair"
            sys.exit(1);
        elif pl_meta == None:
            print "Cannot find metadata for this plugload (possibly undefined?)"
            sys.exit(1);
       
        print "Found device: "+dev.IDstr+" plugload channel %d"%(pl_index)
        
        if (pl_meta.parent == 1):
            print "Error: Plugload is defined as an aggregate sum of plugloads, cannot learn from this (yet!)"
            sys.exit(1);
        
        plugload_row = devicedb.get_devicemetas(where="id=%d"%pl_meta.parent,limit=1);
        
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
    
    if ( len(sys.argv) == 4):
        sid = sys.argv.pop()
        sname = sys.argv.pop()
        pl_meta,dev,pl_index = devicedb.find_plugload(sname,sid)        
        if  pl_index == None:
            print "Cannot find device belonging to this source name/id pair"
            sys.exit(1);
        elif pl_meta == None:
            print "Cannot find metadata for this plugload (possibly undefined?)"
            sys.exit(1);
            
        if pl_meta.parent == 1:
            plids = [int(a) for a in pl_meta.value.split(',')]
            print "Found plugload for "+dev.IDstr+": [",
            for i in plids:
                pl_meta = devicedb.get_devicemetas(where="id=%d"%i,limit=1);
                if len(pl_meta) > 0:
                    print pl_meta[0].value+",",
                    plugnames.append(pl_meta[0].value)
                    plugids.append(i);
                else:
                    print "\nError: no metadata entry for id=%d"%i
                    sys.exit(1);
                    
            print "]"
        else:
            pl_meta = devicedb.get_devicemetas(where="id=%d"%pl_meta.parent,limit=1);
            print "Found plugload for "+dev.IDstr+": "+pl_meta[0].value
            plugnames.append(pl_meta[0].value);
            plugids.append(pl_meta[0].ID);
    
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
    mfid.write("# state_no,"+','.join(plugnames)+','+','.join(['%s (mean)'%s for s in plugnames])+','+','.join(['%s (variance)'%s for s in plugnames])+'\n');
    sfid = open(state_fname,"w");
    sfid.write("# State file\n");
    sfid.write("# state_no,count,mean,variance\n");
    for s in range(nStates):
        modulus = 1;
        mfid.write('%d'%s);
        cnt_acc = 0;
        mean_acc = 0.;
        var_acc = 0.;
        mstr = ''
        vstr = ''
        for i in range(len(plugids)):
            div = modulus;
            modulus *= len(states_list[i]);
            plstate = ( s % modulus ) / div;
            st = states_list[i][plstate]
            cnt_acc += st.counts;
            mean_acc += st.counts * st.mean;
            var_acc += st.counts * st.variance;
            
            mfid.write(',%d'%plstate)
            mstr += ',%.12f'%st.mean
            vstr += ',%.12f'%st.variance
            
        
        mean_acc /= cnt_acc;
        var_acc /= cnt_acc;
        sfid.write("%d,%d,%.15e,%.15e\n"%(s,cnt_acc,mean_acc,var_acc));
        mfid.write(mstr+vstr+'\n');
        
    mfid.close();
    sfid.close();
elif op == 'mapstate':
    ret,j,sys.argv = utils.check_arg(sys.argv,'--rawdata',1)
    if ret:
        rawfname = j[0]
    else:
        rawfname = None
        
    ret,j,sys.argv = utils.check_arg(sys.argv,'--invr',1)
    if ret:
        invr = float(j[0])
    else:
        invr = 1.0
    
    if ( len(sys.argv) != 3 ):
        print "Invalid number of arguments";
        sys.exit(1);
        
    import random, math
    outcsv = sys.argv.pop()
    rmap_fname = sys.argv.pop()
    incsv = sys.argv.pop()
    
    mdata,meta,headers = utils.readcsv(rmap_fname, readmeta=True,readheader=True);
    
    nDev = (len(mdata[0])-1)/3;
    
    if headers == None:
        headers = [''] + ['Device %d'%(d+1) for d in range(nDev)]
       
    print "Read %d states representing %d devices."%(len(mdata),nDev)
       
    rmap = {}
    for row in mdata:
        rmap[row[0]] = row[1:]
    
    idata = utils.readcsv(incsv);
    print "Read %d data points."%len(idata)
    
    if rawfname:
        rawdata = utils.readcsv(rawfname)
        if (len(rawdata) != len(idata)):
            print "Error: len(rawdata) != len(input data)"
            sys.exit(1)
            
        print "Read %d data points of rawdata"%len(rawdata)
    
    fout = open(outcsv,"w");
    devnames = headers[1:1+nDev];
    fout.write("# Disaggregated state output file\n");
    fout.write("# t,"+','.join(['%s (state)'%s for s in devnames])+','+','.join(['%s (est.)'%s for s in devnames])+'\n');
    
    cachemap = {}
    last_log = time.time();
    for rowi in range(len(idata)):
        if time.time()-last_log > 2:
            utils.log_prog(1,1,"Estimate Device Power","%.2f%%"%(100.*rowi/len(idata)))
            last_log = time.time()
        
        row = idata[rowi]
        if rawfname:
            raw = rawdata[rowi]
            
        if row[1] in rmap:
            m = rmap[row[1]];
            means = [m[i+nDev] for i in range(nDev)]
            variances = [m[i+2*nDev] for i in range(nDev)]
            
            if rawfname:
                est = utils.compute_ML_gaussiansum_estimates(raw[1]/invr,means,variances,cachemap=cachemap,cachekey=row[1]);
            else:
                est = [random.gauss(means[i],sqrt(variances[i])) for i in range(nDev)]
            
            fout.write("%.5f,"%row[0] + ','.join(['%d'%i for i in m[0:nDev]]) + ',' + ','.join(['%.12f'%v for v in est]) + '\n')
        else:
            print "Error at t=%.2f. State %d not found.\n"%(row[0],row[1])
            
        
    fout.close();
else:
    print "Command "+op+" not recognized"
    sys.exit(1);