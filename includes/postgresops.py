import psycopg2, os, sys

if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."

import config

def connect():
    global dbcon,dbcur
    dbcon = psycopg2.connect(database=config.map['postgres']['database'], 
                            user=config.map['postgres']['user'], 
                            password=config.map['postgres']['password'])
    dbcur = dbcon.cursor()  

def connected():
    try:
        return not dbcon.closed
    except:
        return False


evil_chars = ['\x00','\n','\r','\\',"'",'"','\x1a']

def check_evil(str):
    for ch in str:
        if ch in evil_chars:
            raise Exception("SECURITY VIOLATION string \"%s\" contains possible SQL INJECTION"%(str))

def check_and_create_schema(schemaname):
    check_evil(schemaname)
    dbcur.execute("SELECT schema_name from information_schema.schemata where schema_name='%s'"%schemaname)
    if dbcur.rowcount == None or dbcur.rowcount <= 0:
        dbcur.execute("CREATE schema "+schemaname)
        dbcon.commit();
        return True
    return False

def check_and_create_table(tabname,columns):
    # security
    check_evil(tabname);
    for nm,ty in columns:
        check_evil(nm)
        check_evil(ty)    
    
    fulltabname = tabname
    if ('.' in tabname):
        schema = tabname[0:tabname.index('.')]
        tabname = tabname[tabname.index('.')+1:]
        check_and_create_schema(schema)
    else:
        schema = None
    
    if schema != None:
        dbcur.execute("SELECT column_name from information_schema.COLUMNS where table_name=%s and table_schema=%s;",(tabname,schema))
    else:
        dbcur.execute("SELECT column_name from information_schema.COLUMNS where table_name=%s;",(tabname,))
        
    if dbcur.rowcount == None or dbcur.rowcount <= 0: # we can create the table then
        varstr = ''
        for nm,ty in columns:
            varstr += "%s %s,"%(nm,ty)
        varstr = varstr[:-1]
        sqlstr = dbcur.mogrify("CREATE TABLE %s (%s);"%(fulltabname,varstr))
        print sqlstr
        dbcur.execute(sqlstr)
        dbcon.commit();
        return True
    
    names = [r[0] for r in columns]
    mismatch = False
    for name, in dbcur:
        if ( name in names ):
            names.remove(name)
        else:
            print "Table %s, oldfmt had column %s, but newfmt doesn't"%(fulltabname,name)
            mismatch = True
    
    for name in names:
        print "Table %s, newfmt had column %s, but oldfmt doesn't"%(fulltabname,name)
        mismatch = True
    
    if mismatch:
        dbcur.execute("SELECT table_name from information_schema.TABLES where table_name like '%s_oldfmt%%'"%(tabname))
        maxoldfmt = -1;
        for name, in dbcur:
            num = int(name[len(tabname+"_oldfmt"):])
            if ( num > maxoldfmt ):
                maxoldfmt = num
        newtab = tabname+"_oldfmt%03d"%(maxoldfmt+1)
        print "Moving table %s to %s"%(fulltabname,newtab)
        dbcur.execute("ALTER TABLE %s RENAME TO %s"%(fulltabname,newtab))
        varstr = ''
        for nm,ty in columns:
            varstr += "%s %s,"%(nm,ty)
        varstr = varstr[:-1]
        sqlstr = dbcur.mogrify("CREATE TABLE %s (%s);"%(fulltabname,varstr))
        print sqlstr
        dbcur.execute(sqlstr)
        dbcon.commit();
        return True
    
    return False

            