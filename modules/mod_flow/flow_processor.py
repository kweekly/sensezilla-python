#!/usr/bin/python

import sys,os, time
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime
import tempfile
from mod_scheduler import scheduledb

class File:pass

class Step:pass

class FlowDef:
    def __init__(self):
        pass
    
    def run(self, time_from, time_to, source_name=None, source_id=None, pretend=False):
        if source_name == None:
            names = utils.list_sources();
            for name in names:
                ids = utils.list_ids(name)
                for id in ids:
                    self.run(time_from, time_to, name, id, pretend)
                return
                            
        elif source_id == None:
            ids = utils.list_ids(source_name)
            for id in ids:
                self.run(time_from, time_to, source_name, id, pretend)
            return
        
        smap = utils.read_source(source_name)
        
        # create all the files we'll need
        if ( self.use_tmp ):
            dir = '/tmp/sensezilla/flowdata/'+self.name
        else:
            dir = config.map['global']['data_dir']+'/flowdata/'+self.name
        
        if not pretend:
            try:
                os.makedirs(dir+'/outputs',0755)
            except:pass
            
        
        for file in self.files:
            if 'OUTPUT' not in [v[0] for v in file.dests]:
                if not pretend:
                    tfile = tempfile.NamedTemporaryFile('w', dir=dir, delete=False)
                    file.fname = tfile.name;
                    tfile.close()
                else:
                    file.fname = os.tempnam(dir)
            else:
                file.fname = dir+'/outputs/%s.O%d_%s_%s_%d_to_%d'%(file.src.name,file.index,source_name,source_id.replace('/','.'),
                                                                   utils.date_to_unix(time_from),utils.date_to_unix(time_to))
                if not pretend:
                    fout = open(file.fname,'w')
                    fout.close()
                
            #print "Created file : "+file.fname


        # generate dictionary of substitutions
        subs = [
                ('TIME_FROM',int(utils.date_to_unix(time_from))),
                ('TIME_TO',int(utils.date_to_unix(time_to))),
                ('SOURCE',source_name),
                ('DEVICE',source_id)                
        ]
        
        for key,val in smap.items():
            if ( type(val) is str ):
                subs.append(('SOURCE.'+key,val))

        if not scheduledb.connected():
            scheduledb.connect();
            
        for step in self.steps:
            cmd = step.cmd;
            for subk,subv in subs:
                cmd = cmd.replace('%%{%s}'%subk,str(subv))
            
            # do file subs
            ofile = None;
            for file in self.files:
                if ( file.src == step ):
                    ofile = file
                    cmd = cmd.replace('%%O%d'%file.index,file.fname)
                else:
                    for destn,desti in file.dests:
                        if ( destn == step ):
                            cmd = cmd.replace('%%I%d'%desti,file.fname)
                
            #print '\n'+cmd+'\n'
            task = scheduledb.Task()
            task.command = cmd
            task.status = scheduledb.WAITING_FOR_START
            task.profile_tag = step.profile
            if ofile == None: 
                task.log_file = '/dev/null'
            else:
                task.log_file = ofile.fname+'.log'
            step.task = task
            
        for step in self.steps:
            for file in self.files:
                for destn,desti in file.dests:
                    if ( destn == step ):
                        step.task.prerequisites.append( file.src.task.id )
        
        for step in self.steps:
            print "Inserting task %d : %s\n"%(step.task.id, step.task.command)
            if not pretend:
                scheduledb.add_task(step.task)
            

def read_flow_file(fname):
    lmap = config.read_struct(config.map['global']['flow_dir']+'/'+fname+".flow");
    if ( lmap == None ):
        raise ValueError("Could not load flow:"+fname)

    flow = FlowDef();
    flow.name = fname
    flow.source_types = lmap['source_types']
    flow.use_tmp = False if not lmap.has_key('use_tmp') or lmap['use_tmp']=='0' else True
    flow.files = []
    flow.steps = []
    for tsk in lmap['tasks']:
        step = Step()
        step.name = tsk
        step.profile = lmap[tsk+'.profile']
        if step.profile not in [i[0:i.find(',')] for i in config.map['mod_scheduler']['profiles']]:
            print "ERROR: profile tag %s not found in config files"%step.profile
            sys.exit(1)
            
        step.cmd = lmap[tsk+'.cmd']
        flow.steps.append(step)
        
    for step in flow.steps:
        # look for output files
        idx = -1
        while ( True ):
            idx = step.cmd.find('%O',idx+1)
            if idx == -1: break
            file = File()
            file.src = step
            file.dests = []
            file.index = int(step.cmd[idx+2:idx+3])
            flow.files.append(file)
            
    for step in flow.steps:
        # look for input files
        idx = -1
        while ( True ):
            idx = step.cmd.find('%I',idx+1)
            if idx == -1: break
            outspec = lmap[step.name+'.'+step.cmd[idx+1:idx+3]]
            found = False
            for file in flow.files:
                idx2 = outspec.find('.')
                if ( file.src.name == outspec[0:idx2] and file.index == int(outspec[idx2+2:idx2+3])):
                    found = True
                    file.dests.append((step,int(step.cmd[idx+2:idx+3])))
                    break
                
            if ( not found ):
                print "ERROR: Couldn't find output "+outspec
                sys.exit(1)
    
    index = 0
    for file in flow.files:
        if ( file.src.name+'.O%d'%file.index in lmap['outputs'] ):
            found = True
            file.dests.append(('OUTPUT',index))
            index += 1
            break
                
    for file in flow.files:
        if ( len(file.dests) == 0 ):
            print "WARNING: Task %s.O%d is not connected to anything"%(file.src.name, file.index)
            
    return flow