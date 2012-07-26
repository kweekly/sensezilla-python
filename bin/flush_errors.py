#!/usr/bin/python
import sys,os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime, timedelta
from mod_flow import filedb,flowdb
from mod_scheduler import scheduledb
import postgresops

def flush_tasks():
    scheduledb.connect()
    idstokill = []
    postgresops.dbcur.execute("select id from schedule.tasks where status>=%s",(scheduledb.ERROR_CRASH,))
    rows = postgresops.dbcur.fetchall()
    idstocheck = [i[0] for i in rows] 
    while len(idstocheck)>0:
        id = idstocheck.pop()
        postgresops.dbcur.execute("select id from schedule.tasks where %s=any(prerequisites)",(id,))
        idstocheck.extend([i[0] for i in postgresops.dbcur])
        idstokill.append(id)
        
    if len(idstokill)==0: return
        
    if not autoconfirm:
        print "The following tasks will be removed from the database: ",idstokill
        conf = raw_input("Confirm [y|n]? ")
        if ( conf != 'y' and conf != 'yes'):
            print "Cancelled by user"
            sys.exit(10)
            
    for id in idstokill:
        str = postgresops.dbcur.mogrify("DELETE FROM schedule.tasks WHERE id=%s",(id,))
        print str
        postgresops.dbcur.execute(str)
        
    postgresops.dbcon.commit()
    print "";

def flush_files():
    scheduledb.connect()
    filedb.connect()
    
    idstokill = []
    postgresops.dbcur.execute("select id from flows.files where status=%s",(filedb.FAIL,))
    idstokill.extend([i[0] for i in postgresops.dbcur])
    
    postgresops.dbcur.execute("select id,task_id from flows.files where status=%s",(filedb.INVALID,))
    rows = postgresops.dbcur.fetchall()
    for id,task_id in rows:
        postgresops.dbcur.execute("select status from schedule.tasks where id=%s",(task_id,))
        if ( postgresops.dbcur.rowcount <= 0 or postgresops.dbcur.fetchone()[0] >= scheduledb.ERROR_CRASH ):
            idstokill.append(id)
            
    if len(idstokill)==0: return
    
    if not autoconfirm:
        print "The following files will be removed from the cache: ",idstokill
        conf = raw_input("Confirm [y|n]? ")
        if ( conf != 'y' and conf != 'yes'):
            print "Cancelled by user"
            sys.exit(10)
            
    for id in idstokill:
        str = postgresops.dbcur.mogrify("DELETE FROM flows.files WHERE id=%s",(id,))
        print str
        postgresops.dbcur.execute(str)
        
    postgresops.dbcon.commit()
    print "";

def flush_flows():
    scheduledb.connect()
    filedb.connect()
    flowdb.connect()
    
    postgresops.dbcur.execute("select flowdef,time_from,time_to,source_name,source_id from flows.curflows where status=%s",(flowdb.ERROR,))
    idstokill = []
    idstokill.extend(postgresops.dbcur.fetchall())
    
    postgresops.dbcur.execute("select flowdef,time_from,time_to,source_name,source_id,task_ids,file_ids from flows.curflows where status!=%s",(flowdb.DONE,))
    rows = postgresops.dbcur.fetchall()
    for flowdef,time_from,time_to,source_name,source_id,task_ids,file_ids in rows:
        found_death= False
        for task_id in task_ids:
            postgresops.dbcur.execute("select status from schedule.tasks where id=%s",(task_id,))
            if ( postgresops.dbcur.rowcount <= 0 or postgresops.dbcur.fetchone()[0] >= scheduledb.ERROR_CRASH ):
                idstokill.append((flowdef,time_from,time_to,source_name,source_id))
                found_death = True
                break
        
        if found_death:
            continue
        
        for file_id in file_ids:
            postgresops.dbcur.execute("select status from flows.files where id=%s",(file_id,))
            if ( postgresops.dbcur.rowcount <= 0 or postgresops.dbcur.fetchone()[0] == filedb.FAIL ):
                idstokill.append((flowdef,time_from,time_to,source_name,source_id))
                found_death = True
                break
            
    if len(idstokill)==0: return

    if not autoconfirm:
        print "The following flows will be removed from the database:\n"+"\n\t".join([i.__str__() for i in idstokill])
        conf = raw_input("Confirm [y|n]? ")
        if ( conf != 'y' and conf != 'yes'):
            print "Cancelled by user"
            sys.exit(10)
            
    for flowdef,time_from,time_to,source_name,source_id in idstokill:
        str = postgresops.dbcur.mogrify("DELETE FROM flows.curflows WHERE flowdef=%s and time_from=%s and time_to=%s and source_name=%s and source_id=%s",
                                        (flowdef,time_from,time_to,source_name,source_id))
        print str
        postgresops.dbcur.execute(str)
        
    postgresops.dbcon.commit()
    print "";        
    
            

sys.argv = sys.argv[1:]

if ( len(sys.argv) == 0):
    print """
Usage: flush_errors.py [tasks | files | flows | all] [--autoconfirm]
    
    tasks : Flush crashed and timed-out tasks from database. Propagate to tasks which depend on them
    
    files : Flush FAIL files from database and files which depend on missing tasks.
    
    flows : Flush flows which cannot complete due to FAIL'd or missing files, or composed of crashed or missing tasks.
    
    all : Do all three in that order
"""
else:
    autoconfirm = len(sys.argv)>1 and sys.argv[1] == '--autoconfirm' 
    if sys.argv[0] == 'tasks' :
        flush_tasks()
    elif sys.argv[0] == 'files' :
        flush_files()
    elif sys.argv[0] == 'flows' :
        flush_flows()
    elif sys.argv[0] == 'all':
        flush_tasks()
        flush_files()
        flush_flows()