import os
import sys
import time
import psutil
import cgi

from jinja2 import *

def do_index(environ, start_response):
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    template = env.get_template('index.html')
    start_response('200 OK',[('Content-Type','text/html')])
    
    ## getting CPU info
    cpu_info = psutil.cpu_percent(interval=1, percpu=True)
    phymem_info = psutil.phymem_usage()
    virtmem_info = psutil.virtmem_usage()
    disk_info = psutil.disk_usage('/mnt/DATA')
    
    ## getting status of modules
    mod_exec_IF.connect();
    if ( mod_exec_IF.connected() ):
        procs = mod_exec_IF.list();
        for mod in procs:
            if mod.state == mod_exec_IF.RUNNING:
                mod.statestr = 'RUN'
            elif mod.state == mod_exec_IF.RESTARTING:
                mod.statestr = 'RESTART'
            elif mod.state == mod_exec_IF.STOPPED:
                mod.statestr = 'STOPPED'
    else:
        procs = []
        
    return [str(template.render(
                  cpu_info=cpu_info,phymem_info=phymem_info,virtmem_info=virtmem_info,disk_info=disk_info,
                  procs_connected=mod_exec_IF.connected(), procs=procs
                  ))]    


def do_admin(environ, start_response):
    start_response('200 OK',[('Content-Type','text/html')])
    resp = ['<html><head><meta http-equiv="Refresh" content="10;url=/index.html" /></head><body>']
    resp.append("<h2>Admin Command Progress</h2>\n<pre>\n");
    d = cgi.parse_qs(environ['QUERY_STRING'])
    if ( 'modname' in d ):
        if ( 'action' in d ):
            resp.append("Module command: %s\n"%d['action'][0]);
            resp.append("Module name: %s\n\n"%d['modname'][0])
            
            if d['modname'][0] == 'mod_exec' and d['action'][0] == 'start': # different procedure
                mod_exec_IF.connect();
                if ( mod_exec_IF.connected() ):
                    resp.append("mod_exec already responding, please kill first if you wish to restart")
                else:
                    rcode = os.system(config.map['mod_exec']['python']+' '+config.map['global']['root_dir']+'/modules/mod_exec/mod_exec.py')
                    resp.append("Started mod_exec, response code %d"%rcode)
            else:
                resp.append("Connect to mod_exec...")
                mod_exec_IF.connect();
                if ( mod_exec_IF.connected() ):
                    resp.append("success.\n")
                    
                    if d['modname'][0] == 'mod_exec' and d['action'][0] == 'stop':
                        mod_exec_IF.kill()
                        resp.append("Killed mod_exec and all modules")
                    else:                    
                        curstate = mod_exec_IF.get_state(d['modname'][0])
                        if curstate != None:
                            resp.append("Current module state is %d\n"%curstate)
                            if ( d['action'][0] == 'start' ):
                                mod_exec_IF.start(d['modname'][0])
                                resp.append("Module started\n")
                            elif (d['action'][0] == 'stop' ):
                                mod_exec_IF.stop(d['modname'][0])
                                resp.append("Module stopped\n")
                            elif (d['action'][0] =='restart'):
                                mod_exec_IF.restart(d['modname'][0])
                                resp.append("Module restarted\n")
                        else:
                            resp.append("Could not get state of %s (is it unknown to mod_exec?)"%d['modname'][0])                    
                else:
                    resp.append("fail.\n")
        else:
            resp.append("No action given\n")
    else:
        resp.append("Cannot determine what admin command you want to run\n")
   
    resp.append("\n\nRedirecting to index.html...\n");
    resp.append("</pre><a href='/index.html'>Or go there now</a></body></html>\n") 
    return resp


def application(environ, start_response):
    global config, mod_exec_IF
    
    if 'SENSEZILLA_DIR' not in os.environ:
        if 'SENSEZILLA_DIR' not in environ:
            print "Note: SENSEZILLA_DIR not provided. Assuming "+environ['DOCUMENT_ROOT']+"/.."
            environ['SENSEZILLA_DIR'] = environ['DOCUMENT_ROOT']+"/.."
        os.environ['SENSEZILLA_DIR'] = environ['SENSEZILLA_DIR']
        
        sys.path.insert(0,environ['SENSEZILLA_DIR']+"/includes");
    import config
    from mod_exec import mod_exec_IF
    
    req = environ['PATH_INFO']
    
    if ( req == '/index.html'):
        return do_index(environ,start_response)    
    elif (req == '/admin.html'):
        return do_admin(environ,start_response)
    else:
        start_response('301 Redirect', [('Location', '/index.html')]);
        return []
    

    
    


