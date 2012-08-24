import os
import sys
import time
import psutil
import cgi 
 
from jinja2 import * 

import tempfile, subprocess, shlex
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
     
