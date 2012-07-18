# -*- coding: utf-8 -*-
# load the config file
import sys, os;


# set stdout & stderr to unbuffered
try:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0) 
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0) 
except AttributeError:pass
 
if 'SENSEZILLA_DIR' not in os.environ:
	print "Note: SENSEZILLA_DIR not provided. Assuming ../"
	os.environ['SENSEZILLA_DIR'] = ".."

root = os.environ['SENSEZILLA_DIR']

message_dir = root+"/messages"
module_dir = root+"/modules"
include_dir = root+"/includes"
mission_dir = root+"/conf"

#include all directories
sys.path.insert(0,root);
sys.path.insert(0,message_dir);
sys.path.insert(0,module_dir);
sys.path.insert(0,include_dir);
sys.path.insert(0,mission_dir);

if ('SENSEZILLA_MISSION' not in os.environ) :
	print "Note: The environment variable SENSEZILLA_MISSION not defined. Using 'server'"
	mission = "server"
else:
	mission = os.environ['SENSEZILLA_MISSION']

message_types = []
# import all types of messages
for f in os.listdir(message_dir):
	module_name, ext = os.path.splitext(f) # Handles no-extension files, etc.
	if ext == '.py': # Important, ignore .pyc/other files.
		#module = __import__(module_name)  
		message_types.append(module_name);
        

class IPCMap:
    def __init__(self, oldmap={}, modname=None):
        self.modname = modname;
        self.innermap = {};
        for key,val in oldmap.items():
            self[key] = val;
        
    def __getitem__(self, key):
        if ( self.innermap.has_key(key) ) :
            return self.innermap[key];
        
        # if this is the top-level map
        if(self.modname == None):
            self.innermap[key] = IPCMap(modname=key);
            return self.innermap[key];
        
        else:
            if ( not mod_config_IF.connected() ):
                mod_config_IF.connect();
            
            # couldn't connect, probably not running, load from file
            if ( not mod_config_IF.connected() ):
                force_load()
                if (self.innermap.has_key(key)):
                    return self.innermap[key];
                else:
                    return None;
                
            # needs to contact mod_config
            val = mod_config_IF.getVal(self.modname, key);
            if ( val != None ):
                self.innermap[key] = val;
                
            return val;
        
    # note : This only updates the local copy!
    def __setitem__(self, index, item):
        self.innermap[index] = item;
    
    # note : only keys from the local cache!
    def keys(self):
        return self.innermap.keys();
        
    def has_key(self,key):
        return self[key] != None;
        
    def items(self):
        return self.innermap.items();


map = IPCMap({'global':IPCMap({'root_dir':root,'message_dir':message_dir, 'module_dir':module_dir, 'include_dir':include_dir, 'mission_dir':mission_dir},modname='global')});


def check_key( mod_name, key):
    if map.has_key(mod_name):
        return map[mod_name].has_key(key);
    else:
        return False;


from mod_config import mod_config_IF;


def load_conf(conf_file, verbose=False):
    import re
    global map

    cmap = map;
    #map = {}
    cur_mod = 'global'
    wsexpr = re.compile(r"^\s*$");
    comexpr = re.compile(r"^(?P<line>.*?)#.*$")
    sectexpr = re.compile(r"^\s*\[(?P<sect>.+?)\]\s*$");
    incexpr = re.compile(r"^\s*include\s+\"(?P<file>.*?)\"\s*$");
    expr = re.compile(r"^\s*(?P<key>\S+)\s*(?P<oper>\S+?)\s*(?P<val>\S+)\s*$");
    expr2 = re.compile(r"^\s*(?P<key>\S+)\s*(?P<oper>\S+?)\s*\"(?P<val>.*?)\"\s*$");
    try :
        f = open(conf_file,'r');
        line_no = 0;
        for line in f:
            line = line.rstrip();
            line_no += 1;
                
            match = comexpr.match(line);
            if match :
                cline = match.group('line');
            else:
                cline = line;

            if ( wsexpr.match(cline) ):
                continue;
            
            sectmatch = sectexpr.match(cline);
            if sectmatch :
                cur_mod = sectmatch.group('sect');
                continue;
                
            incmatch = incexpr.match(cline);
            if incmatch :
                if incmatch.group('file')[0] == '/':
                    load_conf(incmatch.group('file'),verbose);
                else:
                    load_conf(root+"/conf/"+incmatch.group('file'),verbose);
                continue;
                
            for key in cmap['global'].keys():
                cline = cline.replace("$("+key+")", cmap['global'][key]);
            
            if cmap.has_key(cur_mod):
                for key in cmap[cur_mod].keys():
                    if type(cmap[cur_mod][key]).__name__ == 'str':
                        cline = cline.replace("$("+key+")", cmap[cur_mod][key]);
                
            match = expr.match(cline);
            match2 = expr2.match(cline);
            
            if match2 :
                key = match2.group('key');
                val = match2.group('val');
                oper = match2.group('oper');
            elif match :
                key = match.group('key');
                val = match.group('val');
                oper = match.group('oper');
            else:
                print conf_file+":",line_no,": Syntax error \""+line+"\""
                continue;
            
            if oper == '=' :
                if cmap.has_key(cur_mod) and cmap[cur_mod].has_key(key):
                    if (verbose): print conf_file+":",line_no,": Already contains key (overriding) \""+key+"\"";
                else:
                    if (verbose): print conf_file+":"+"["+cur_mod+"] Setting "+key+" to \""+val+"\""; 

                if not cmap.has_key(cur_mod):
                    cmap[cur_mod] = {key:val}
                    #print "%s.%s = %s"%(cur_mod,key,val)
                else:
                    cmap[cur_mod][key] = val;
                    #print "%s.%s = %s"%(cur_mod,key,val)
                    
            elif oper == '@=' :
                if cmap.has_key(cur_mod) and cmap[cur_mod].has_key(key):
                    if (verbose): print conf_file+":",line_no,": Already contains array (overriding) \""+key+"\"";
                else:
                    if (verbose): print conf_file+":"+"["+cur_mod+"] Setting "+key+" to [\""+val+"\"]"; 

                if not cmap.has_key(cur_mod):
                    cmap[cur_mod] = {key:[val]}
                else:
                    cmap[cur_mod][key] = [val];                
            elif oper == '@+' :
                if cmap.has_key(cur_mod) and cmap[cur_mod].has_key(key):
                    if (verbose): print conf_file+":"+"["+cur_mod+"] Appending to "+key+" value [\""+val+"\"]"; 
                else:
                    conf_file+":",line_no,": Array does not exist \""+key+"\"" 

                if not cmap.has_key(cur_mod):
                    cmap[cur_mod] = {key:[val]}
                else:
                    if not cmap[cur_mod].has_key(key):
                        cmap[cur_mod][key] = [val]
                    else:
                        cmap[cur_mod][key].append(val); 
            else :
                print conf_file+":",line_no,": Invalid operator '"+oper+"'"

    except IOError, msg:
        print "ERROR: Could not load config file ",conf_file,":",msg

    # if file doesn't exist then f.close() will fail
    try:
        f.close()
    except:
        pass

def force_load():
    global map
    # remove all instances of IPCMap
    map = map.innermap;
    for key in map.keys():
        if isinstance(map[key],IPCMap):
            map[key] = map[key].innermap;
    
    try:
        idx = sys.argv.index("-c");
    except:
        idx = -1
        
    if idx != -1:
        print "Config file override: "+sys.argv[idx+1]
        load_conf(sys.argv[idx+1]); 
    else:
        load_conf(mission_dir+"/"+mission+".conf");
        
    
def subs_range(pt):
	retval = []
	idx1 = pt.find('[')
	idx2 = pt.find('-',idx1)
	idx3 = pt.find(']',idx2)
	try:
		if idx1 != -1 and idx2 != -1 and idx3 != -1:
			for i in range(int(pt[idx1+1:idx2]), int(pt[idx2+1:idx3])+1):
				retval.append(pt[0:idx1] + str(i) + pt[idx3+1:]) 
		else:	
			retval.append(pt)
	except Exception as ex:
		print ex
		retval.append(pt)
	return retval

    
try:
	idx = sys.argv.index("-c");
except:
	idx = -1
	
if idx != -1:
	force_load();

