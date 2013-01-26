# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import time, os, sys
import config

CACHE_TIMEOUT = 5

source_struct_cache = {}
source_timeouts = {}
device_struct_cache = {}
device_timeouts = {}

def str_to_date(dstr):
    try:
        posix = int(dstr)
        return datetime.utcfromtimestamp(posix)
    except ValueError:pass
    
    try:
        if (dstr[0] == '-'):
            return datetime.utcnow() - str_to_interval(dstr[1:])
    except ValueError:pass
    
    raise ValueError('Unrecognized date string '+dstr)
    
def str_to_interval(dstr):
    try :
        if ':' in dstr:
            pts = dstr.split(':')
            if ( len(pts) == 2 ):
                return timedelta(hours=int(pts[0]),minutes=int(pts[1]))
            elif ( len(pts) == 3):
                return timedelta(hours=int(pts[0]),minutes=int(pts[1]),seconds=int(pts[2]))
        else:
            if 'm' in dstr or 'h' in dstr or 's' in dstr or 'd' in dstr or 'w' in dstr or 'y' in dstr:
                secs = 0;
                nm = '';
                for ch in dstr:
                    if ( ch >= '0' and ch <= '9' ):
                        nm += ch
                    else:
                        if ( ch == 's' ):
                            secs += int(nm)
                        elif(ch == 'm' ):
                            secs += 60 * int(nm)
                        elif(ch == 'h' ):
                            secs += 60 * 60 * int(nm)
                        elif(ch == 'd' ):
                            secs += 24 * 60 * 60 * int(nm)
                        elif(ch == 'w' ):
                            secs += 7 * 24 * 60 * 60 * int(nm)
                        elif(ch == 'y'):
                            secs += 365 * 24 * 60 * 60 * int(nm)
                        else:
                            raise ValueError()
                return timedelta(seconds=secs)
            
            raise ValueError();
    except ValueError:
        raise ValueError('Unrecognized interval string '+dstr)
    
def date_to_str(dat):
    return dat.strftime('%m/%d/%Y %H:%M:%S')
    
def date_to_unix(dat):
    return time.mktime(dat.utctimetuple())

def list_sources():
    ret = []
    for file in os.listdir(config.map['global']['source_dir']):
        if ( file.endswith('.src') ):
            name = file[file.find('/')+1:-4]
            ret.append(name)
    return ret

def list_devicedefs():
    ret = []
    for file in os.listdir(config.map['global']['device_dir']):
        if ( file.endswith('.dev') ):
            name = file[file.find('/')+1:-4]
            ret.append(name)
    return ret

def read_source(source,use_cache=True):
    if source in source_struct_cache and use_cache and time.time() < source_timeouts[source] + CACHE_TIMEOUT:
        return source_struct_cache[source]
    else:
        source_struct_cache[source] = config.read_struct(config.map['global']['source_dir']+'/'+source+".src");
        source_timeouts[source] = time.time()
        return source_struct_cache[source]
 
def read_device(device,use_cache=True):
    if device in device_struct_cache and use_cache and time.time() < device_timeouts[device] + CACHE_TIMEOUT:
        return device_struct_cache[device]
    else:
        device_struct_cache[device] = config.read_struct(config.map['global']['device_dir']+'/'+device+".dev");
        device_timeouts[device] = time.time()
        return device_struct_cache[device]
 
def check_arg(argv,arg,nvals=0):
    try:
        i = argv.index(arg)
        vals = argv[i+1:i+nvals+1]
        argv = argv[0:i] + argv[i+nvals+1:]
        return True,vals,argv
    except:pass
    return False,[],argv
        
def hexify(str):
    return ''.join(['%02X'%ord(i) for i in str]);

def unhexify(str):
    return ''.join([chr(int(str[i:i+2],16)) for i in range(0,len(str),2)])

def undecify(str):
    return unhexify(hex(str)[2:])

def strip0s(str):
    i = 0
    while i < len(str):
        if (ord(str[i]) != 0):
            return str[i:]
        i += 1;
    return '\x00'
    
def readcsv(fname, strings=False, readmeta=False, readheader=False):
    fin = open(fname,"r");
    rows = []
    meta = []
    for line in fin:
        line = line.lstrip();
        if ( len(line) == 0):
            continue;
            
        if (line[0] == '#'):
            meta.append(line[1:])
            continue;
        
        pts = line.split(',');
        row = []
        for pt in pts:
            if strings:
                row.append(pt.rstrip().lstrip())
            else:
                row.append(float(pt.rstrip().lstrip()))
        rows.append(row)
        
    fin.close();
    
    if not readmeta and not readheader:
        return rows
    else:
        headers = None
        for m in meta:
            if m.count(',') == len(rows[0])-1:
                m = m.lstrip().rstrip()
                headers = m.split(',');
                break
        
        retv = (rows,)
        if readmeta:
            retv += (meta,)
        if readheader:
            retv += (headers,)
        
        return retv;
        

# S = X1 + X2 + ...  + XN
# where X1...XN are gaussian random variables with given means and variances
# Guess what the values of X1..XN are, given S
# cachemap should be a dict to be repeatedly given as a cache
# cachekey should be the same for any pair of the same means and variances
def compute_ML_gaussiansum_estimates(S,means,variances,cachemap={},cachekey=None):
    import numpy
    import numpy.linalg as la
    
    nDev = len(means);
    if nDev == 1:
        return [S]
        
    # see if the matrix Ainv is available
    if cachekey and cachekey in cachemap and 'A' in cachemap[cachekey]:
        Ainv = cachemap[cachekey]['Ainv']
    else:
        A = numpy.ones((nDev-1,nDev-1)) * -1.0/(variances[nDev-1]);
        for i in range(nDev-1):
            A[i,i] -= 1.0/(variances[i]);
            
        Ainv = la.inv(A)
        if cachekey:
            if cachekey not in cachemap:
                cachemap[cachekey] = {}
            cachemap[cachekey]['Ainv'] = Ainv
            
    b = numpy.ones((nDev-1,1)) * 1.0/variances[nDev-1] * (S - means[nDev-1]);
    for i in range(nDev-1):
        b[i,0] += means[i]/variances[i];
        
    x = numpy.dot(Ainv, -b);
    retv = list(x[:,0]) + [S - numpy.sum(x)];
    for i in range(len(retv)):
        if ( retv[i] < 0 ):
            means.pop(i)
            variances.pop(i)
            if cachekey:
                cachekey = str(cachekey) + 'r' + str(i)
            retv = compute_ML_gaussiansum_estimates(S,means,variances,cachemap={},cachekey=cachekey);
            retv.insert(i,0.);
            return retv
    
    return retv;
    
def log_prog(step_current,step_total,step_name,step_progress_str):
    print "PROGRESS STEP %d OF %d \"%s\" %s DONE"%(step_current,step_total,step_name,step_progress_str)
