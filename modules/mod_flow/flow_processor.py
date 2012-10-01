#!/usr/bin/python
# -*- coding: utf-8 -*-

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
import shlex

class File:pass

class Step:pass

class FlowDef:
    def __init__(self):
        pass
    
    def run(self, time_from, time_to, source_name=None, source_id=None, pretend=False, use_cache=True, local=False, params=[]):
        if source_id == None and local:
            print "Error: Can only run 'local' test on one stream ( source name & id pair ) at a time"
            sys.exit(1)
        
        
        if source_name == None:
            names = utils.list_sources();
            for name in names:
                ids = utils.list_ids(name)
                for id in ids:
                    self.run(time_from, time_to, name, id, pretend, use_cache, local)
            return
                            
        elif source_id == None:
            ids = utils.list_ids(source_name)
            for id in ids:
                self.run(time_from, time_to, source_name, id, pretend, use_cache, local)
            return
        
        smap = utils.read_source(source_name)
        if not local and use_cache:
            # find any cached files
            import filedb
            filedb.connect()
            
            for file in self.files:
                stepchain = file.stepchain
                cfiles = filedb.get_files(where='time_from=%s and time_to=%s and source_name=%s and source_id=%s and steps=%s',params=(time_from,time_to,source_name,source_id,stepchain))
                for cfile in cfiles:
                    if ( cfile.status == filedb.INVALID or os.path.exists(cfile.file_name) ):
                        file.cached = True
                        file.file_id = cfile.id
                        file.fname = cfile.file_name
                        file.deptask = cfile.task_id
                        file.stepchain = stepchain
                        print "Found cached file for output of "+file.src.name
                        break
        
            # prune any tasks that don't need to be run
            for step in self.steps[:]:
                canbepruned = True
                for f in step.outputs:
                    if not f.cached:
                        canbepruned = False
                        break 
                if canbepruned:
                    print "Pruning step %s because the cache can supply all outputs"%step.name
                    self.steps.remove(step)
                else:
                    for f in step.outputs:
                        if f.cached:
                            f.cached = False
                            print "Cached file %s.O%d will be regenerated b/c not all outputs were cached"%(step.name,f.index)
        
        # create all the files we'll need
        if local:
            dir = ''
        else:
            if ( self.use_tmp ):
                dir = '/tmp/sensezilla/flowdata/'+self.name
            else:
                dir = config.map['global']['data_dir']+'/flowdata/'+self.name
        
        
            if not pretend:
                try:
                    os.makedirs(dir+'/outputs',0755)
                except:pass
            
        
        for file in self.files:
            if not file.cached:
                if local:
                    file.fname = dir+'testing_%s_%s.O%d'%(self.name,file.src.name,file.index)
                    if not pretend:
                        if file.directory:
                            try:
                                os.mkdir(file.fname)
                            except:pass
                        else:
                            fout = open(file.fname,'w')
                            fout.close()
                else:
                    if 'OUTPUT' not in [v[0] for v in file.dests]:
                        if not pretend:
                            if file.directory:
                                file.fname = tempfile.mkdtemp(dir=dir)
                            else:
                                tfile = tempfile.NamedTemporaryFile('w', dir=dir, delete=False)
                                file.fname = tfile.name;
                                tfile.close()
                        else:
                            file.fname = os.tempnam(dir)
                    else:
                        file.fname = dir+'/outputs/%s.O%d_%s_%s_%d_to_%d'%(file.src.name,file.index,source_name,source_id.replace('/','.'),
                                                                           utils.date_to_unix(time_from),utils.date_to_unix(time_to))
                        if file.directory:
                            if not pretend:
                                os.mkdir(file.fname)
                        else:
                            if not pretend: 
                                fout = open(file.fname,'w')
                                fout.close()
                    
                if file.directory:
                    print "Created directory : "+file.fname
                else:
                    print "Created file : "+file.fname


        # generate dictionary of substitutions
        subs = {
                'TIME_FROM':int(utils.date_to_unix(time_from)),
                'TIME_TO':int(utils.date_to_unix(time_to)),
                'SOURCE':source_name,
                'ID':source_id                
        };
        subs.update(params)
        
        try:
            import devicedb
            devicedb.connect()
            plmeta,dev,pl_index = devicedb.find_plugload(source_name,source_id)
            subs['PLUGLOAD'] = plmeta.value;
            subs['DEVID'] = dev.ID
            subs['DEVIDSTR'] = dev.IDstr
            
        except Exception,e:
            print "Cannot contact devicedb "+str(e)
        
        for key,val in smap.items():
            if ( type(val) is str ):
                subs['SOURCE.'+key] = val;
        
        def procsub(s):
            i = s.find('%{')
            if i == -1:
                return s
            cnt = 0
            s = s[0:i] + procsub(s[i+2:]);
            i2 = s.find('}',i)
            s2 = s[i:i2]
            repl = '';
            if ( s2[0] == '?' ):
                pts = s2.split(':');
                if ( len(pts) != 3 ):
                    print "Error parsing flow file ternary statement: "+s2
                else:
                    if ( pts[0] == '?' ):
                        repl = pts[2]
                    else:
                        repl = pts[1]
            elif s2 in subs:
                repl = str(subs[s2])
                
            return s[0:i] + repl + s[i2+1:];
        
        for step in self.steps:
            cmd = step.cmd;
            
            cmd = procsub(cmd)
            
            # do file subs
            if len(step.outputs) > 0:
                ofile = step.outputs[0];
            else:
                ofile = None
            
            for file in step.outputs:
                if file.directory:
                    cmd = cmd.replace('%%O%dD'%file.index,file.fname)
                else:
                    cmd = cmd.replace('%%O%d'%file.index,file.fname)
                    
            for file in step.inputs:
                for dests,desti in file.dests:
                    if dests==step:
                        if file.directory:
                            cmd = cmd.replace('%%I%dD'%desti,file.fname)
                        else:
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
            for file in step.inputs:
                if not file.cached:
                    step.task.prerequisites.append( file.src.task.id )
                else:
                    step.task.prerequisites.append( file.deptask )
        
        if local:
            for s in self.steps:                
                s.done = False
                
            import subprocess
            
            def runstep(s):
                if s.done:
                    return
                
                for tid in s.task.prerequisites:
                    for s2 in self.steps:
                        if s2.task.id == tid:
                            runstep(s2)
                                
                
                # all prereqs ran
                if not s.done:
                    print "Executing %s\n"%(s.task.command)
                    if not pretend:
                        if 0 != subprocess.call(shlex.split(s.task.command)):
                            raise Exception("Error running step %s"%s.name)
                        
                    s.done = True
            
            for s in self.steps:
                runstep(s)
            
            print "DONE RUNNING FLOW"                   
                
        else:
            if not scheduledb.connected():
                scheduledb.connect();
                
            for step in self.steps:
                print "Inserting task %d : %s\n"%(step.task.id, step.task.command)
                if not pretend:
                    scheduledb.add_task(step.task)
                    
            for mfile in self.files:
                if not mfile.cached:
                    print "Inserting file %s.%d : %s\n"%(mfile.src.name,mfile.index,mfile.fname)
                    if not pretend:
                        file = filedb.File()
                        mfile.file_id = file.id
                        file.file_name = mfile.fname
                        file.directory = mfile.directory
                        file.time_from = time_from
                        file.time_to = time_to
                        file.source_name = source_name
                        file.source_id = source_id
                        file.steps = mfile.stepchain
                        file.status = filedb.INVALID
                        file.task_id = mfile.src.task.id
                        filedb.add_file(file)
                     
            print "Inserting flow %s(%s,%s,%s,%s)"%(self.name,time_from,time_to,source_name,source_id)
            if not pretend:
                import flowdb
                flow = flowdb.Flow()
                flow.flowdef = self
                flow.time_from = time_from
                flow.time_to = time_to
                flow.source_name = source_name
                flow.source_id = source_id
                flow.task_ids = [t.task.id for t in self.steps]
                flow.file_ids = [f.file_id for f in self.files]
                flow.status = flowdb.RUNNING
                flowdb.add_flow(flow)

def read_flow_file(fname):
    if not fname.endswith('.flow'):
        fname = config.map['global']['flow_dir']+'/'+fname+".flow"
        
    lmap = config.read_struct(fname);
    if '/' in fname:
        fname = fname[fname.rfind('/')+1:]
    
    if fname.endswith('.flow'):
        fname = fname[:-5]
    
    if ( lmap == None ):
        raise ValueError("Could not load flow: "+fname)

    flow = FlowDef();
    flow.name = fname
    flow.source_types = lmap['source_types']
    flow.use_tmp = False if not lmap.has_key('use_tmp') or lmap['use_tmp']=='0' else True
    flow.files = []
    flow.steps = []
    flow.outputs = []
    for tsk in lmap['tasks']:
        step = Step()
        step.name = tsk
        step.outputs = []
        step.inputs = []
        step.profile = config.getdict(lmap,tsk+'.profile','cpu_bound')
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
            file.cached = False
            step.outputs.append(file)
            file.src = step
            file.dests = []
            file.index = int(step.cmd[idx+2:idx+3])
            if len(step.cmd) > idx+3 and step.cmd[idx+3] == 'D':
                file.directory = True
            else:
                file.directory = False
                
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
                    step.inputs.append(file)
                    file.dests.append((step,int(step.cmd[idx+2:idx+3])))
                    if len(step.cmd) > idx+3 and step.cmd[idx+3] == 'D' and not file.directory:
                        print "ERROR: Output file %d from %s was specified as a directory, but task %s believes its not"%(file.index,file.src.name,step.name)
                        sys.exit(1)
                    break
                
            if ( not found ):
                print "ERROR: Couldn't find output "+outspec
                sys.exit(1)
    
    if 'outputs' in lmap:
        index = 0
        for file in flow.files:
            if ( file.src.name+'.O%d'%file.index in lmap['outputs'] ):
                found = True
                file.dests.append(('OUTPUT',index))
                flow.outputs.append(file)
                index += 1
                break
    
        # now prune any steps/files not needed
        for step in flow.steps:
            step.mark = False
        for file in flow.files:
            file.mark = False
    
        def mark_recursive(file):
            file.src.mark = True
            file.mark = True
            for f in file.src.inputs:
                mark_recursive(f)
    
        for file in flow.outputs:
            mark_recursive(file)
        
        for step in flow.steps[:]:
            if not step.mark:
                print "Pruning step %s: no connection to output"%(step.name)
                flow.steps.remove(step)
    
        for file in flow.files[:]:
            if not file.mark:
                print "Pruning file %s.O%d : no connection to output"%(file.src.name,file.index)
                flow.files.remove(file)
    else:
        print "No outputs in flow definition, all tasks are run"
    
    def build_file_dep_str(file):
        return file.src.name+'('+','.join([build_file_dep_str(f) for f in file.src.inputs])+')'
        
    for file in flow.files:
        file.stepchain = build_file_dep_str(file)    
    
    if (len(flow.steps) <= 0 ):
        raise Exception("ERROR: No steps left after pruning")    
    
    for file in flow.files:
        if ( len(file.dests) == 0 ):
            print "WARNING: Task %s.O%d is not connected to anything"%(file.src.name, file.index)
            
    return flow
