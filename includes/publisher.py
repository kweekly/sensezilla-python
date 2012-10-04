# -*- coding: utf-8 -*-
import time
import config
import utils
import devicedb
import postgresops
import uuid
import os

from smap import core, server, util
from twisted.python import log
from twisted.internet import reactor
import threading
import sys

#log.startLogging(sys.stdout)

DEFAULT_NEW_DEVICE = config.map['publisher']['default_new_device']
CREATE_NEW_DEVICE = True if config.map['publisher']['create_new_device'].lower() == 'true' else False
DEFAULT_NEW_SOURCE = config.map['publisher']['default_new_source']

FLUSH_INTERVAL = float(config.map['publisher']['flush_interval'])
CACHE_TIMEOUT = 5

SMAP_UUID = config.map['publisher']['smap_UUID']
SMAP_DATAFILE = config.map['global']['data_dir'] + '/' + 'smap_datafile'

device_cache = {}

smap_instances = {}

def gen_source_ids(device, devdef=None):
    struct = utils.read_source(device.source_name)
    if not devdef:
        devdef = utils.read_device(device.device_type)
    num = len(devdef['feeds'])
    driver = struct['driver'];
    retval = []
    if driver  == "SMAP":
        for i in range(num):
            retval.append(str(uuid.uuid5(uuid.UUID(SMAP_UUID), str("%s/%d"%(device.IDstr,i)))))
        return retval
    elif driver == "CSV":
        for i in range(num):
            retval.append('%s/%s.csv'%(device.IDstr,devdef['feeds'][i]))
        return retval
    else:
        print "ERROR Cannot generate source ID for %s b/c no %s driver"%(device.source_name,driver)
        return []
    
def find_device(id_str, create_new=False, device_type=None, source=None, devdef=None ):
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
                dev.source_ids = gen_source_ids(dev,devdef)
                devicedb.insert_device(dev)
            else:
                print "Error publishing data : %s is not in devicedb"%id_str
                return None
        else:
            dev = dev[0]
            if (devdef != None and len(dev.source_ids) < len(devdef['feeds'])):
                dev.source_ids = gen_source_ids(dev,devdef)
            
        dev.birth = time.time()
        device_cache[id_str] = dev        
        
    return dev

def publish_smap(source_name,sourcedef,dev,devdef,feednum,devuuid,time,data):
    if source_name not in smap_instances:
        if not reactor.running:
            print "Starting twistd reactor"
            th = threading.Thread(target=lambda: reactor.run(installSignalHandlers=0))
            th.daemon = True
            th.start()

        inst = core.SmapInstance(SMAP_UUID,reportfile=SMAP_DATAFILE)
        rpt = {
               'ReportDeliveryLocation' : [sourcedef['url']+'/add/'+sourcedef['apikey']],
               'ReportResource' : '/+',
               'uuid' : inst.uuid('report 0')
        }
        if not inst.reports.update_report(rpt):
            inst.reports.add_report(rpt)
        inst.reports.update_subscriptions()
        inst.start()
        smap_instances[source_name] = inst
    else:
        inst = smap_instances[source_name]     
    
    uuido = uuid.UUID(devuuid)
    ts = inst.get_timeseries(uuido)
    if ts == None:
        print "add ts: "+'/'+dev.IDstr+'/'+str(devdef['feeds'][feednum]);
        ts = inst.add_timeseries('/'+dev.IDstr+'/'+str(devdef['feeds'][feednum]),uuido,devdef['feeds'][feednum],data_type='double',milliseconds=False)
        smapmeta = {'Instrument/ModelName' : devdef['name'],
                    'Instrument/DeviceDefinition' : dev.device_type,
                    'Instrument/ID' : dev.IDstr,
                    'Instrument/FeedIndex' : str(feednum),
                    'Instrument/FeedName' : str(devdef['feeds'][feednum]) }
        locmeta = devicedb.get_devicemetas(where="key='LOCATION' and %d=any(devices)"%dev.ID,limit=1)
        if len(locmeta) > 0:
            smapmeta['Location/CurrentLocation'] = locmeta[0].value

        usermeta = devicedb.get_devicemetas(where="key='USER' and %d=any(devices)"%dev.ID,limit=1)
        if len(usermeta) > 0:
            smapmeta['Extra/User'] = usermeta[0].value
            
        inst.set_metadata(uuido, smapmeta)
    
    if ( isinstance(time,list) ):
        for i in range(len(time)):
            ts.add(time[i],data[i])
    else:
        ts.add(time,data)

last_flush = time.time()
def tick():
    global last_flush
    if time.time() - last_flush > FLUSH_INTERVAL:
       flush()

       last_flush = time.time() 
       
def flush(timeout=30):
    global smap_instances
    st = time.time()
    while time.time()-st < timeout:
        busy = False
        for inst in smap_instances.values():
            inst.reports.flush()
            for sub in inst.reports.subscribers:
                if sub['Busy']:
                    busy = True
                    
        if not busy:
            break;
        
        time.sleep(1);
    

def publish_data(id_str, time, data, feednum=None, devdef=None, device_type=None, source=None):    
    # Usage 1: time and data are scalars - one data point, feed # = feednum or 0 if feednum=None
    # Usage 2: time and data are lists of scalars (time could also be scalar) - one data point per feed, feed #s = feednum (list) or range(total feeds) if feednum=None
    # Usage 3: time and data are lists of scalars, feednum is a scalar - multiple data points for one feed
    # Usage 4: time and data are lists of lists of scalars (time could also be list of scalar) - multiple data points per feed, feed #s = feednum(list) or range(total feeds) if feednum=None
    if not isinstance(data, list): # Usage 1
        data = [data]
        if feednum == None:
            feednum = [0]
        else:
            feednum = [feednum]
    else:  # Usage 2,3,4
        if feednum == None: # Usage 2,4
            feednum = range(len(data))
        elif not isinstance(feednum,list): # usage 3
            feednum = [feednum]
            time = [time]
            data = [data]
    
    if not isinstance(time,list) or (not isinstance(time[0],list) and isinstance(data[0],list)): # Usage 1,2,4
        time = [time]*len(feednum)
        
    if not devicedb.connected():
        devicedb.connect()
    
    id_str = id_str.replace('/','_');
    postgresops.check_evil(id_str);
    
    dev = find_device(id_str, create_new = True, device_type=device_type, source=source, devdef=devdef)

    if dev == None:
        return;
    
    source_struct = utils.read_source(dev.source_name)
    if devdef == None:
        devdef = utils.read_device(dev.device_type)
        
    driver = source_struct['driver']
    for i in range(len(feednum)):
        if feednum[i] >= len(devdef['feeds']):
            print "ERROR cannot publish data for feed %d because it is not defined in the definition for %s"%(feednum[i],dev.source_name)
        elif feednum[i] >= len(dev.source_ids) or dev.source_ids[feednum[i]] == None or dev.source_ids[feednum[i]] == '':
            print "ERROR cannot publish data for feed %d of device %s because it is not defined"%(feednum[i],dev.IDstr)
        else:
            source_id = dev.source_ids[feednum[i]]
            if driver == 'SMAP':
                publish_smap(dev.source_name,source_struct,dev,devdef,feednum[i],source_id,time[i],data[i])
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
                    if isinstance(time[i],list):
                        for j in range(len(time[i])):
                            csvfile.write("%.12f,%.12f\n"%(time[i][j],data[i][j]))
                    else:
                        csvfile.write("%.12f,%.12f\n"%(time[i],data[i]))
                    csvfile.close()
                except OSError,e:
                    print "ERROR Cannot publish data to %s because "%(fname),e
                    
            else:
                print "ERROR Cannot publish data for %s b/c no %s driver"%(dev.source_name,driver)
                return []       
