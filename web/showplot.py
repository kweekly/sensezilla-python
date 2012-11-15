import os
import sys
import time
import psutil
import cgi 
import utils
 
from jinja2 import * 

import tempfile, subprocess, shlex

import datetime as DT

def do_showliveplot(environ,start_response):
    start_response('200 OK',[('Content-Type','text/html')])
    url = "/showplot?"+environ['QUERY_STRING'];
    return [("<html><script>\n"
             "function updateImg() {\n"
             "document.images[\"plot\"].src=\""+url+"\" + \"&junk=\" + (new Date()).getTime();\n"
             "setTimeout(\"updateImg()\", 2000);\n}\n"
             "setTimeout(\"updateImg()\",1000);\n"
             "</script>\n"
             "<body>\n"
             "<img name=plot src=\""+url+"\">\n"
             "</body>\n"
             "</html>\n")]
    
def do_showplot(environ,start_response):
    import config
    d = cgi.parse_qs(environ['QUERY_STRING'])
    
    if 'id' in d:
        from mod_flow import filedb
        import postgresops
        try :
            filedb.connect();
            postgresops.check_evil(d['id'][0])
            files = filedb.get_files(where = 'id = %s'%d['id'][0])
            if ( len(files) != 1): 
                raise Exception("Error 0 or >1 files matched!")
            else:
                f = tempfile.NamedTemporaryFile(delete = False)
                fname = f.name
                f.close();
                cmdline = str(config.map['web']['plotcsvcmd'] + "-csvin %s -pngout %s -title \"Source:%s ID:%s Filters:%s\"" %(files[0].file_name,fname,files[0].source_name,files[0].source_id,files[0].steps))
                cmds = shlex.split(cmdline)
                subprocess.call(cmds)
                if os.path.getsize(fname) == 0:
                    raise Exception("Plot file not created. Error plotting?")
                
                start_response('200 OK',[('Content-Type','image/png')])
                return TempFileWrapper(fname);
        except Exception,exp:
            import traceback
            start_response('500 ERROR',[('Content-Type','text/plain')])
            return ["Exception "+str(exp)+" occured\n",traceback.format_exc()]
    elif 'source' in d and 'sourceid' in d:
        try :
            source = d['source'][0]
            sourceid = d['sourceid'][0]
            if 'len' in d:
                tfrom = DT.datetime.now() - DT.timedelta(seconds=int(d['len'][0]))
            else:
                tfrom = DT.datetime.now() - DT.timedelta(seconds=60*10)
            
            tto = DT.datetime.now()
  
            f = tempfile.NamedTemporaryFile(delete = False)
            fname = f.name
            f.close()
            
            fcsv = tempfile.NamedTemporaryFile(delete = False)
            fcsvname = fcsv.name
            fcsv.close()
            
            cmdline = str(config.map['web']['fetchcmd'] + " fetch --plot %s --from %d --to %d %s %s %s"%(fname,utils.date_to_unix(tfrom),utils.date_to_unix(tto),source,sourceid,fcsvname))
            print cmdline
            cmds = shlex.split(cmdline)
            subprocess.call(cmds)
            
            if os.path.exists(fcsvname):
                os.unlink(fcsvname);
                
            if os.path.getsize(fname) == 0:
                raise Exception("Plot file not created. Error plotting?")
                           
            start_response('200 OK',[('Content-Type','image/png')])
            return TempFileWrapper(fname);
                
        except Exception,exp:
            import traceback
            start_response('500 ERROR',[('Content-Type','text/plain')])
            return ["Exception "+str(exp)+" occured\n",traceback.format_exc()]        
        


class TempFileWrapper(object):
    def __init__(self,fname,blksize=8192):
        self.fp = open(fname,'r')
        self.fname = fname;
        self.blksize = blksize
        
    def __iter__(self):
        return self
    
    def next(self):
        data = self.fp.read(self.blksize)
        if data:
            return data
        raise StopIteration
    
    def close(self): 
        self.fp.close()
        os.unlink(self.fname)
     
