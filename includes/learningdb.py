# -*- coding: utf-8 -*-
import utils
import postgresops
import random
from datetime import *


def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected();
    
def initdb():
    res = postgresops.check_and_create_table(
         "learning.hmmgaussianemissions",
         (("plugload_id", "integer"),
          ("data_from","timestamp"),
          ("data_to","timestamp"),
          ("state_ids","integer[]"),
          ("counts","integer[]"),
          ("means","real[]"),
          ("variances","real[]"),
          ))


def insertHMMGaussianEmissions(plugload_id,timefrom,timeto,stateids,counts,means,variances):
    if timefrom and timeto:
        postgresops.dbcur.execute("INSERT INTO learning.HMMGaussianEmissions (plugload_id,data_from,data_to,state_ids,counts,means,variances) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                    (plugload_id,timefrom,timeto,stateids,counts,means,variances));
    else:
        postgresops.dbcur.execute("INSERT INTO learning.HMMGaussianEmissions (plugload_id,state_ids,counts,means,variances) VALUES (%s,%s,%s,%s,%s)",
                                    (plugload_id,stateids,counts,means,variances));
    
    postgresops.dbcon.commit();


class HMMGaussianState:
    def __init__(self,sid,c,m,v):
        self.state_id = sid
        self.counts = c;
        self.mean = m
        self.variance = v
        
    def __str__(self):
        return "(ID:%d,Counts:%d,mean:%.2e,variance:%.2e)"%(self.state_id,self.counts,self.mean,self.variance)

def getHMMGaussianEmissionIDs():
    postgresops.dbcur.execute("SELECT distinct(plugload_id) FROM learning.HMMGaussianEmissions");
    ret = []
    for row in postgresops.dbcur:
        ret.append(row[0]);
    return ret;

def getHMMGaussianEmissions(plugload_id):
    postgresops.dbcur.execute("SELECT state_ids,counts,means,variances FROM learning.HMMGaussianEmissions WHERE plugload_id=%s ORDER BY data_from DESC",(plugload_id,))
    entries = []
    
    for row in postgresops.dbcur:
        entry = [HMMGaussianState(row[0][i],row[1][i],row[2][i],row[3][i]) for i in range(len(row[0]))]
        entry.sort(key=lambda e:e.state_id);
        entries.append(entry)
        
    return entries
    
def computeGlobalHMMGaussianParameters(entries, maxStates=10, binThresh=1.2):
    # flatten everything and sort
    for l in entries:
        l.sort(key=lambda e:e.mean)
    
    statelist = []
    stateid = 0;
    while True:
        lowest = None
        lremove = None
        for l in entries:
            if len(l) > 0 and (lowest==None or l[0].mean < lowest.mean):
                lowest = l[0];
                lremove = l;
        if ( lowest == None ):
            break;
            
        lremove.pop(0);
        lowest.state_id = stateid;
        statelist.append(lowest)
        stateid += 1;
    
    # first group states by binThresh
    i = 0;
    while i < len(statelist) - 1:
        if statelist[i+1].mean / statelist[i].mean < binThresh:
            #group into the same bin
            st = statelist.pop(i+1)
            statelist[i].mean = (statelist[i].mean * statelist[i].counts + st.mean * st.counts)/(statelist[i].counts + st.counts);
            statelist[i].variance = (statelist[i].variance * statelist[i].counts + st.variance * st.counts)/(statelist[i].counts + st.counts);
            statelist[i].counts = statelist[i].counts + st.counts;
        else:
            i += 1;
        
    
    # remove down to maxStates
    while len(statelist) > maxStates:
        mindiff = 0;
        for i in range(len(statelist)-1):
            if ( statelist[i+1]/statelist[i] < statelist[mindiff+1]/statelist[mindiff]) :
                mindiff = i;
                
        i = mindiff;
        st = statelist.pop(i+1)
        statelist[i].mean = (statelist[i].mean * statelist[i].counts + st.mean * st.counts)/(statelist[i].counts + st.counts);
        statelist[i].variance = (statelist[i].variance * statelist[i].counts + st.variance * st.counts)/(statelist[i].counts + st.counts);
        statelist[i].counts = statelist[i].counts + st.counts;
    
    stateid = 0;
    for s in statelist:
        s.state_id = stateid;
        stateid += 1;
        
    return statelist;