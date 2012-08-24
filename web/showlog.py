import os
import sys
import time
import psutil
import cgi 

from jinja2 import * 
 
def do_showlog(environ,start_response):
    import config
    import postgresops
    from mod_scheduler import scheduledb
    
    
    start_response('200 OK',[('Content-Type','text/html')])
    resp = ['<html><body>\n']
    d = cgi.parse_qs(environ['QUERY_STRING'])
    if 'taskid' in d:
        import postgresops
        from mod_scheduler import scheduledb
        try:
            scheduledb.connect()
            postgresops.check_evil(d['taskid'][0])
            resp.append("<h2>Log File for Task ID: %s</h2>\n<pre>\n"%d['taskid'][0]);
            task = scheduledb.get_tasks(where='id = %s'%(d['taskid'][0]),orderby="start_time desc")
            if ( len(task) != 1):
                resp.append("Error 0 or >1 tasks matched!")
            else:
                fin = open(task[0].log_file,'r')
                resp.extend(fin.readlines())
                fin.close()
        except Exception,exp:
            resp.append("Exception "+str(exp)+" occurred")
            
        resp.append("</pre>\n")
    else:
        resp.append("<h2>Last 100 lines of log file for python modules</h2>\n")
        resp.append("<pre>\n")
        stdin,stdout = os.popen2("tail -n 100 "+config.map['mod_exec']['logfile'])
        stdin.close(); resp.extend(stdout.readlines()); stdout.close();
        resp.append("</pre>\n")  
    
    resp.append('</body></html>')
    return resp