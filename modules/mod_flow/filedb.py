import psycopg2, os, sys
import config
import utils
import postgresops
import random
from datetime import *

(
INVALID,
VALID
) = range(2)



class File:
    def __init__(self):
        self.id = next_file_id();
        self.file_name = ''
        self.directory = False
        self.time_from = datetime.now();
        self.time_to = datetime.now();
        self.source_name = ''
        self.source_id = ''
        self.steps = []
        self.status = INVALID
        self.task_id = 0
        

def connect():
    postgresops.connect()
    
def connected():
    return postgresops.connected()

def initdb():
    res = postgresops.check_and_create_table(
         "flows.files",
         (("id", "integer primary key"),
          ("file_name", "varchar"),
          ("directory", "boolean"),
          ("time_from","timestamp"),
          ("time_to","timestamp"),
          ("source_name","varchar"),
          ("source_id","varchar"),
          ("steps","varchar[]"),
          ("status","integer"),
          ("task_id","integer")
          ))
    
def next_file_id():
    while True:
        newint = id_rgen.randint(0, 2**31-1)
        postgresops.dbcur.execute("SELECT id from flows.files where id=%s limit 1",(newint,))
        if ( postgresops.dbcur.rowcount == None or postgresops.dbcur.rowcount <= 0):
            break
    
    return newint    
    
    
def add_file(file):
    postgresops.dbcur.execute("INSERT INTO flows.files"+ 
                "(id, file_name, directory, time_from, time_to, source_name, source_id, steps, status, task_id) "+
                "VALUES ("+"%s,"*9+"%s)",row_for_file(file))
    postgresops.dbcon.commit()
    
def update_entire_file(file):
    postgresops.dbcur.execute("UPDATE flows.files SET"+
                              "id=%s, file_name=%s, directory=%s, time_from=%s, time_to=%s, source_name=%s source_id=%s, steps=%s, status=%s, task_id=%s where id=%s",
                                row_for_task(task)+[file.id])
    postgresops.dbcon.commit()
    
def update_file(file,field_name,field_val):
    postgresops.check_evil(field_name);
    postgresops.dbcur.execute("UPDATE flows.files SET "+field_name+"=%s where id=%s",
                              (field_val,file.id))
    postgresops.dbcon.commit()
    
def update_file_mult(file,fields):
    for field,val in fields:
        postgresops.check_evil(field);
        
    postgresops.dbcur.execute("UPDATE flows.files SET "+",".join([field+"=%s" for field,val in fields])+" where id=%s",
                              [val for field,val in fields]+[file.id])
    postgresops.dbcon.commit()
    

def get_files(where='',orderby='',limit=None):
    extra = ''
    if where != '':
        extra += ' WHERE '+where
    if orderby != '':
        extra += ' ORDER BY '+orderby
    if limit != None:
        extra += ' LIMIT %d'%limit
    
    retval = []
    
    postgresops.dbcur.execute("SELECT * from flows.files"+extra+";")

        
    rows = postgresops.dbcur.fetchall()
    for row in rows:
        retval.append(file_for_row(row))
        
    return retval

def count(where=''):
    if where != '':
        postgresops.dbcur.execute("SELECT count(*) from flows.files WHERE "+where+";")
    else:
        postgresops.dbcur.execute("SELECT count(*) from flows.files;")
        
    return postgresops.dbcur.fetchone()[0];

def row_for_file(file):
    return ( file.id, file.file_name, file.directory, file.time_from, file.time_to, file.source_name, file.source_id, file.steps, file.status, file.task_id )
    
def file_for_row(row):
    file = File()
    ( file.id, file.file_name, file.directory, file.time_from, file.time_to, file.source_name, file.source_id, file.steps, file.status, file.task_id ) = row;
    return file
    

    