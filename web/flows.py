import cgi

from jinja2 import * 
   
def do_flows(environ,start_response):
    import config
    from mod_flow import flowdb
    from mod_scheduler import scheduledb
    import postgresops
    from tasks import apply_status_task
    
    
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
