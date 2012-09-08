import time
import config
import utils
import devicedb
import postgresops
import uuid
import os


DEFAULT_NEW_DEVICE = config.map['publisher']['default_new_device']
CREATE_NEW_DEVICE = True if config.map['publisher']['create_new_device'].lower() == 'true' else False
DEFAULT_NEW_SOURCE = config.map['publisher']['default_new_source']

CACHE_TIMEOUT = 5

device_cache = {}

def gen_source_ids(device):
    struct = utils.read_source(device.source_name)
    devdef = utils.read_device(device.device_type)
    num = len(devdef['feeds'])
    driver = struct['driver'];
    retval = []
    if driver  == "SMAP":
        for i in range(num):
            retval.append(uuid.uuid5(source, "%s/%d"%(device.IDstr,i)))
        return retval
    elif driver == "CSV":
        for i in range(num):
            retval.append('%s/%s.csv'%(device.IDstr,devdef['feeds'][i]))
        return retval
    else:
        print "ERROR Cannot generate source ID for %s b/c no %s driver"%(device.source_name,driver)
        return []
    
def find_device(id_str, create_new=False, device_type=None, source=None ):
    if not devicedb.connected():
        devicedb.connect()
        
    if id_str in device_cache and time.time() < device_cache[id_str].birth + CACHE_TIMEOUT:
        dev = device_cache[id_str]
    else:  
        dev = devicedb.get_devices(where="idstr='%s'"%id_str,limit=1)
        if (len(dev) == 0):
            if CREATE_NEW_DEVICE and create_new:
                dev = devicedb.new_device()
                dev.IDstr = id_str
                dev.device_type = device_type if device_type else DEFAULT_NEW_DEVICE
                dev.source_name = source if source else DEFAULT_NEW_SOURCE
                # generate some random places to dump data
                dev.source_ids = gen_source_ids(dev)
                devicedb.insert_device(dev)
            else:
                print "Error publishing data : %s is not in devicedb"%id_str
                return None
        else:
            dev = dev[0]
            
        dev.birth = time.time()
        device_cache[id_str] = dev        
        
    return dev

def publish_data(id_str, time, data, feednum=None, device_type=None, source=None):    
    if not isinstance(data, list):
        data = [data]
        if feednum == None:
            feednum = [0]
        else:
            feednum = [feednum]
    else:
        if feednum == None:
            feednum = range(len(data))
    
    if not isinstance(time,list):
        time = [time]*len(feednum)
        
    if not devicedb.connected():
        devicedb.connect()
    
    postgresops.check_evil(id_str);
    dev = find_device(id_str, create_new = True)

    if dev == None:
        return;
    
    source_struct = utils.read_source(dev.source_name)
    devdef = utils.read_device(dev.device_type)
        
    driver = source_struct['driver']
    for i in range(len(feednum)):
        if feednum[i] >= len(devdef['feeds']):
            print "ERROR cannot publish data for feed %d because it is not defined in the definition for %s"%(feednum[i],dev.source_name)
        elif dev.source_ids[feednum[i]] == None or dev.source_ids[feednum[i]] == '':
            print "ERROR cannot publish data for feed %d of device %s because it is not defined"%(feednum[i],dev.IDstr)
        else:
            source_id = dev.source_ids[feednum[i]]
            if driver == 'SMAP':
                pass
            elif driver == 'CSV':
                fname = source_id
                if fname[0] != '/':
                     fname = source_struct['path'] + '/' + fname
                
                try:
                    parentdir = fname[:fname.rfind('/')]
                    
                    try:
                        os.makedirs(parentdir)
                    except: pass
                    
                    csvfile = open(fname, "ab")
                    #print "\t",time[i],data[i]
                    csvfile.write("%.12f,%.12f\n"%(time[i],data[i]))
                    csvfile.close()
                except OSError,e:
                    print "ERROR Cannot publish data to %s because "%(fname),e
                    
            else:
                print "ERROR Cannot publish data for %s b/c no %s driver"%(dev.source_name,driver)
                return []       