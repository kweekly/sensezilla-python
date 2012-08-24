
import os
import sys
import time
import cgi 

from jinja2 import * 

def do_admin(environ, start_response):
    import config
    from mod_exec import mod_exec_IF
    
    
    start_response('200 OK',[('Content-Type','text/html')])
    resp = ['<html><head><meta http-equiv="Refresh" content="10;url=javascript:window.history.back()" /></head><body>']
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
                    if (os.path.exists('/etc/init.d/sensezilla')):
                        rcode = os.system('/etc/init.d/sensezilla start')
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
    elif ( 'action' in d ):
        if d['action'][0] == 'requeueall':
            from mod_scheduler import scheduledb
            resp.append("Connecting to schedule DB...")
            scheduledb.connect()
            if not scheduledb.connected():
                resp.append("fail.\n")
            else:       
                errortasks = scheduledb.get_tasks(where='status >= %d'%(scheduledb.ERROR_CRASH),orderby="start_time desc")
                for task in errortasks:
                    scheduledb.update_task(task,'status',scheduledb.WAITING_FOR_START)
                return ['<html><script>window.history.back()</script></html>']
            
        elif d['action'][0] == 'requeue':
            from mod_scheduler import scheduledb
            import postgresops
            resp.append("Connecting to schedule DB...")
            scheduledb.connect()
            if not scheduledb.connected():
                resp.append("fail.\n")
            else:
                resp.append("yay\n")
                if 'task' in d:
                    try:
                        postgresops.check_evil(d['task'][0])
                        task = scheduledb.get_tasks(where='status >= %d and id = %s'%(scheduledb.ERROR_CRASH,d['task'][0]),orderby="start_time desc")
                        if ( len(task) != 1):
                            resp.append("Error 0 or >1 tasks matched!")
                        else:  
                            scheduledb.update_task(task[0],'status',scheduledb.WAITING_FOR_START)
                            return ['<html><script>window.history.back()</script></html>']
                    except Exception,exp:
                        resp.append("Exception "+str(exp)+" occurred")                               
                    
                else:
                    resp.append("Did not provide ID\n")
        else:
            resp.append("Unknown action %s\n"%d['action'])
    else:
        resp.append("Cannot determine what admin command you want to run\n")
   
    resp.append("\n\nRedirecting to whence you came...\n");
    resp.append("</pre><a href='javascript:window.history.back()'>Or go there now</a></body></html>\n") 
    return resp
