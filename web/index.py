import os
import sys
import time
import psutil
import cgi

from jinja2 import * 

import config
from mod_exec import  mod_exec_IF


def do_index(environ, start_response):
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    template = env.get_template('index.html')
    start_response('200 OK',[('Content-Type','text/html')])

    ## getting CPU info
    cpu_info = psutil.cpu_percent(interval=1, percpu=True)
    phymem_info = psutil.phymem_usage()
    virtmem_info = psutil.virtmem_usage()
    disk_info = psutil.disk_usage(config.map['global']['data_dir'])
     
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
