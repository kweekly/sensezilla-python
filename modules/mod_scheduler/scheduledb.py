import psycopg2, os, sys
import config
import postgresops
import random
from datetime import *

(
STOPPED,
WAITING_FOR_INPUT,
WAITING_FOR_START,
RUNNING,
PAUSED,
DONE,
ERROR_CRASH,
ERROR_TIMEOUT
) = range(0,8)

id_rgen = random.Random()
id_rgen.seed()

class Task:
    def __init__(self):
        self.id = next_task_id();
        self.command = 'ls'
        self.profile_tag = ''
        self.prerequisites = []
        self.start_after = datetime.fromtimestamp(0)
        self.deadline_s = 10000000
        self.start_time = datetime.now()
        self.end_time = datetime.fromtimestamp(0)
        self.cpu_usage_s = 0
        self.status = STOPPED
        self.progress_steps_done = 0
        self.progress_steps_total = 0
        self.step_description = ''
        self.step_progress_str = ''
        self.log_file = '/dev/null'

def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected()

def initdb():
    res = postgresops.check_and_create_table(
         "schedule.tasks",
         (("id", "integer primary key"),
          ("command","varchar"),
          ("profile_tag","varchar"),
          ("prerequisites","integer[]"),
          ("start_after","timestamp"),
          ("deadline_s","integer"),
          ("start_time","timestamp"),
          ("end_time","timestamp"),
          ("cpu_usage_s","integer"),
          ("status","smallint"),
          ("progress_steps_done","smallint"),
          ("progress_steps_total","smallint"),
          ("step_description","varchar"),
          ("step_progress_str","varchar"),
          ("log_file","varchar")
          ))
    if res: # if a new table was created, create the index
        postgresops.dbcur.execute("CREATE UNIQUE INDEX schedule_tasks_index_%d ON schedule.tasks (start_time)"%(id_rgen.randint(0,2**31-1),))
        postgresops.dbcon.commit()

def next_task_id():
    while True:
        newint = id_rgen.randint(0, 2**31-1)
        postgresops.dbcur.execute("SELECT id from schedule.tasks where id=%s limit 1",(newint,))
        if ( postgresops.dbcur.rowcount == None or postgresops.dbcur.rowcount <= 0):
            break
    
    return newint


def add_task(task):
    postgresops.dbcur.execute("INSERT INTO schedule.tasks"+ 
                "(id,command,profile_tag,prerequisites,start_after,deadline_s,start_time,end_time,cpu_usage_s,status,progress_steps_done,progress_steps_total,step_description,step_progress_str,log_file) "+
                "VALUES ("+"%s,"*14+"%s)",row_for_task(task))
    postgresops.dbcon.commit()
    
def update_task(task,field_name,field_val):
    postgresops.check_evil(field_name);
    postgresops.dbcur.execute("UPDATE schedule.tasks SET "+field_name+"=%s where id=%s",(field_val,task.id))
    postgresops.dbcon.commit()
    
def update_task_mult(task,fields):
    for field,val in fields:
        postgresops.check_evil(field);
        
    postgresops.dbcur.execute("UPDATE schedule.tasks SET "+",".join([field+"=%s" for field,val in fields])+" where id=%s",[val for field,val in fields]+task.id)
    postgresops.dbcon.commit()
    
def get_task_by_id(id):
    postgresops.dbcur.execute("SELECT * from schedule.tasks WHERE id=%s;",(id,))
    if ( postgresops.dbcur.rowcount == None or postgresops.dbcur.rowcount <= 0):
        return None
    return task_for_row(postgresops.dbcur.fetchone())
    
def get_tasks(where=''):
    retval = []
    if where != '':
        postgresops.dbcur.execute("SELECT * from schedule.tasks WHERE "+where+";")
    else:
        postgresops.dbcur.execute("SELECT * from schedule.tasks;")
        
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(task_for_row(row))
        
    return retval

def row_for_task(task):
    return (task.id, task.command, task.profile_tag, task.prerequisites, task.start_after, task.deadline_s, task.start_time, task.end_time, task.cpu_usage_s, task.status,
                 task.progress_steps_done, task.progress_steps_total, task.step_description, task.step_progress_str, task.log_file )
    
def task_for_row(row):
    task = Task()
    (task.id, task.command, task.profile_tag, task.prerequisites, task.start_after, task.deadline_s, task.start_time, task.end_time, task.cpu_usage_s, task.status,
                 task.progress_steps_done, task.progress_steps_total, task.step_description, task.step_progress_str, task.log_file ) = row;
    return task
    
