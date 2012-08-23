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

def apply_status_task(task):
    from mod_scheduler import scheduledb
    if task == None:
        return
    if ( task.status == scheduledb.STOPPED ):
        task.statusstr = "Stopped"
    elif ( task.status == scheduledb.WAITING_FOR_INPUT ):
        task.statusstr = "Waiting for Prerequisite IDs:<br>["+','.join([str(i) for i in task.prerequisites])+"]"
    elif ( task.status == scheduledb.WAITING_FOR_START ):
        task.statusstr = "Waiting until "+task.start_time.strftime("%m/%d/%Y %H:%M:%S")+" to start"
    elif ( task.status == scheduledb.WAITING_FOR_CPU ):
        task.statusstr = "In Queue"
    elif ( task.status == scheduledb.RUNNING ):
        task.statusstr = "Running"
    elif ( task.status == scheduledb.PAUSED ):
        task.statusstr = "Paused"
    elif ( task.status == scheduledb.ERROR_CRASH ):
        task.statusstr = "Crashed"
    elif ( task.status == scheduledb.ERROR_TIMEOUT ):
        task.statusstr = "Timed Out"
    elif ( task.status == scheduledb.DONE ):
        task.statusstr = "Finished"
    
def do_tasks(environ,start_response):
    from mod_scheduler import scheduledb
    
    scheduledb.connect()
    dbconnected = scheduledb.connected()
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    template = env.get_template('tasks.html')
    start_response('200 OK',[('Content-Type','text/html')])

    ## getting task info
    active_tasks = scheduledb.get_tasks(where='status >= %d AND status <= %d'%(scheduledb.WAITING_FOR_INPUT,scheduledb.PAUSED),orderby="status desc")
    error_tasks = scheduledb.get_tasks(where='status >= %d'%(scheduledb.ERROR_CRASH),orderby="end_time desc")
    done_tasks = scheduledb.get_tasks(where='status = %d'%(scheduledb.DONE),orderby="start_time desc",limit=15)
    for task in active_tasks+error_tasks+done_tasks:
        apply_status_task(task)

    return [str(template.render(
                dbconnected=dbconnected,
                active_tasks=active_tasks,
                error_tasks=error_tasks,
                done_tasks=done_tasks
            ))]
    
def do_flows(environ,start_response):
    from mod_flow import flowdb
    from mod_scheduler import scheduledb
    import postgresops
    
    flowdb.connect()
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    template = env.get_template('flows.html')
    start_response('200 OK',[('Content-Type','text/html')])
    
    ## getting flow info
    postgresops.dbcur.execute("SELECT flowdef,time_from,time_to,count(*) from flows.curflows where status=%s group by flowdef,time_from,time_to",(flowdb.RUNNING,))
    active_flows = postgresops.dbcur.fetchall()
    postgresops.dbcur.execute("SELECT flowdef,time_from,time_to,count(*) from flows.curflows where status=%s group by flowdef,time_from,time_to order by time_from desc limit 15 ",(flowdb.DONE,))
    done_flows = postgresops.dbcur.fetchall()

    from mod_flow import filedb
    file_cache_progress = filedb.get_files(where='status=%d'%filedb.INVALID)
    file_cache_done = filedb.get_files(where='status=%d or status=%d'%(filedb.VALID,filedb.FAIL))
    for f in file_cache_progress + file_cache_done:
        if f.status == filedb.INVALID or f.status == filedb.FAIL:
            if f.status == filedb.INVALID:
                f.statusstr = "INVALID"
            else:
                f.statusstr = "FAIL"
            task = scheduledb.get_task_by_id(f.task_id)
            if task != None:
                apply_status_task(task)
                f.idstr = str(f.task_id)+' ('+task.statusstr+')'
            else:
                f.idstr = str(f.task_id)+' (not found)'
        elif f.status == filedb.VALID:
            f.statusstr = "VALID"
            f.idstr = str(f.task_id)

    return [str(template.render(
                active_flows=active_flows,
                done_flows=done_flows,
                file_cache_progress=file_cache_progress,
                file_cache_done=file_cache_done
            ))]

def do_admin(environ, start_response):
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

def do_showlog(environ,start_response):
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
     
import tempfile, subprocess, shlex
def do_showplot(environ,start_response):
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
    
def do_locationbuilder(req,environ,start_response): 
    import devicedb
    devicedb.connect()
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    if ( req == '/locationbuilder' or req == '/locationbuilder/' ):
        req = '/locationbuilder/index'
    
    if '?' in req:
        tempname = req[0:req.find('?')]
    else:
        tempname = req
    
    pagename = tempname[tempname.rfind("/")+1:]
    
    try:
        template = env.get_template(tempname+'.html')
    except TemplateNotFound:
        start_response('404 Not Found',[])
        return [];
        
    start_response('200 OK',[('Content-Type','text/html')])
    
    d = cgi.parse_qs(environ['QUERY_STRING'])
    
    if pagename=='links':   
        metadata = devicedb.get_devicemetas(where="key='LOCATION' and parent=0", orderby="value ASC")
        linkgen = ''
        def radd(parent,level, linkgen):
           newmetas = devicedb.get_devicemetas(where="key='LOCATION' and parent=%d"%parent, orderby="value ASC")
           for met in newmetas: 
               linkgen += "-"*level+" "+"<a target=main href='/locationbuilder/showloc?locid=%d'>"%met.ID+met.value+"</a> ["+\
                                        "<a target=main href='/locationbuilder/showloc?locid=new&parent=%d'"%met.ID+">+</a>]<br>";
               linkgen = radd(met.ID,level+1,linkgen);
           return linkgen  
             
               
        for met in metadata:
             linkgen += "<h3><a target=main href='/locationbuilder/showloc?locid=%d'>"%met.ID+met.value+"</a> [<a target=main href='/locationbuilder/showloc?locid=new&parent=%d'"%met.ID+">+</a>]</h3>\n"
             linkgen = radd(met.ID,1,linkgen)
             
        linkgen += "<h3><a target=main href='/locationbuilder/showloc?locid=new&parent=0'>New location...</a></h3>"
        
        return [str(template.render( linkgen = linkgen ))]
    elif pagename=='showloc':
        
        if 'action' in d and d['action'][0] == 'delete':
            def rdelete(id):
                metadata = devicedb.get_devicemetas(where="parent=%d"%id)
                for met in metadata:
                    rdelete(met.ID);
                devicedb.delete_devicemeta(id)
              
            rdelete(int(d['locid'][0]))
            
            return ['<html><script>window.parent.frames["links"].document.location.reload();\nwindow.location="/locationbuilder/start";</script></html>'];
                       
        if 'parent' in d and d['parent'][0] != '0': 
            parid = int(d['parent'][0]);
            parentloc = devicedb.get_devicemetas(where="id=%d"%parid,limit=1)[0];
        else:
            parentloc = None
            
        if d['locid'][0] == 'new':
            loc = devicedb.new_devicemeta()
            loc.key = "LOCATION"
            loc.value = "New Location"
            if parentloc != None:
                loc.parent = parentloc.ID
            else:
                loc.parent = 0
            devicedb.insert_devicemeta(loc);
        else:
            loc = devicedb.get_devicemetas(where="id=%d"%int(d['locid'][0]),limit=1)[0];
        
        if 'action' in d and d['action'][0] == 'edit':
            post = cgi.FieldStorage(fp=environ['wsgi.input'],environ=environ,keep_blank_values=True);
            loc.value = post['value'].value
            if 'parent' in post and loc.ID != int(post['parent'].value):
                if loc.parent != int(post['parent'].value):
                    parentloc = devicedb.get_devicemetas(where="id=%d"%int(post['parent'].value),limit=1)[0]
                    
                loc.parent = int(post['parent'].value)
                 
            devicedb.update_devicemeta(loc)            
                        
        def radd(parent, level, listgen):
            metadata = devicedb.get_devicemetas(where="key='LOCATION' and parent=%d"%parent, orderby="value ASC")
            for met in metadata:
                if loc.parent == met.ID:
                    seltex = 'selected="selected"'
                else:
                    seltex = ''
                      
                if level > 0:
                    listgen += "<option value=%d"%met.ID+" %s>"%seltex+"-"*level+" "+met.value+"</option>\n";
                else:
                    listgen += "<option value=%d"%met.ID+" %s>"%seltex+"<b>"+met.value+"</b></option>\n";
                listgen = radd(met.ID,level+1,listgen);
            return listgen
            
        listgen = radd(0,0,'')

            
              
        return [str(template.render(loc=loc,listgen=listgen))]
    else:
        return [str(template.render())]

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
    try:
        if ( req == '/index'):
            return do_index(environ,start_response)    
        elif (req == '/admin'):
            return do_admin(environ,start_response)
        elif (req == '/tasks'):
            return do_tasks(environ,start_response)
        elif (req == '/showlog'):
            return do_showlog(environ,start_response)
        elif (req == '/flows'):
            return do_flows(environ,start_response)
        elif (req == '/showplot'):
            return do_showplot(environ,start_response)
        elif (req.startswith("/locationbuilder")):
            return do_locationbuilder(req,environ,start_response)
        else:
            start_response('301 Redirect', [('Location', '/index')]);
            return []
    except Exception, e:
        import traceback
        
        return ["<pre>",traceback.format_exc(),"</pre>"]
    

    
    


