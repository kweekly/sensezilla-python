import cgi

from jinja2 import * 

def apply_status_task(task):
    import config
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
    import config
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