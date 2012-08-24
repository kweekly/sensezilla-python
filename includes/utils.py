from datetime import datetime, timedelta
import time, os, sys
import config

def str_to_date(dstr):
    try:
        posix = int(dstr)
        return datetime.fromtimestamp(posix)
    except ValueError:pass
    
    try:
        if (dstr[0] == '-'):
            return datetime.now() - str_to_interval(dstr[1:])
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
    return time.mktime(dat.timetuple())

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

def read_source(source):
     return config.read_struct(config.map['global']['source_dir']+'/'+source+".src");
 
def read_device(device):
     return config.read_struct(config.map['global']['device_dir']+'/'+device+".dev");
 
def check_arg(argv,arg,nvals=0):
    try:
        i = argv.index(arg)
        vals = argv[i+1:i+nvals+1]
        argv = argv[0:i] + argv[i+nvals+1:]
        return True,vals,argv
    except:pass
    return False,[],argv
        
    