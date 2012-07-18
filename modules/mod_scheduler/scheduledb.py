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
DONE,
ERROR_CRASH,
ERROR_TIMEOUT
) = range(0,7)

id_rgen = random.Random()
id_rgen.seed()

class Task:
    def __init__(self):
        self.id = next_task_id();
        self.command = 'ls'
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
        self.step_percent_done = 0.0

def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected()

def initdb():
    res = postgresops.check_and_create_table(
         "schedule.tasks",
         (("id", "integer primary key"),
          ("command","varchar"),
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
          ("step_percent_done","real")
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
                "(id,command,prerequisites,start_after,deadline_s,start_time,end_time,cpu_usage_s,status,progress_steps_done,progress_steps_total,step_description,step_percent_done) "+
                "VALUES ("+"%s,"*12+"%s)",
                (task.id, task.command, task.prerequisites, task.start_after, task.deadline_s, task.start_time, task.end_time, task.cpu_usage_s, task.status,
                 task.progress_steps_done, task.progress_steps_total, task.step_description, task.step_percent_done ))
    postgresops.dbcon.commit()
    
def get_tasks(where=''):
    retval = []
    if where != '':
        postgresops.dbcur.execute("SELECT * from schedule.tasks WHERE "+where+";")
    else:
        postgresops.dbcur.execute("SELECT * from schedule.tasks;")
        
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        task = Task()
        (task.id, task.command, task.prerequisites, task.start_after, task.deadline_s, task.start_time, task.end_time, task.cpu_usage_s, task.status,
                 task.progress_steps_done, task.progress_steps_total, task.step_description, task.step_percent_done ) = row;
        retval.append(task)
        
    return retval
    
    
