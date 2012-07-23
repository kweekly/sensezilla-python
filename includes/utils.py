from datetime import datetime, timedelta
import time

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