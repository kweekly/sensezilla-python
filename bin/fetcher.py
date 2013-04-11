#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys,os, time, os.path, shutil
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../"
    os.environ['SENSEZILLA_DIR'] = ".."
    
sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
from datetime import datetime, timedelta

if len(sys.argv) < 2:
    print """
Usage: fetcher.py [list | fetch]

    list : List available sources and identifiers        

    fetch [--plot fname.png] [--from <time>] [--to <time>] <source name> <device identifier> <output CSV>
        Fetch data to CSV, default 1 day history, or by given times
"""
elif sys.argv[1] == 'list':
    for file in os.listdir(config.map['global']['source_dir']):
        if ( file.endswith('.src') ):
            name = file[file.find('/')+1:-4]
            print "Source name: "+name
            fmap = config.read_struct(config.map['global']['source_dir']+'/'+file);
            for key,val in sorted(fmap.items()):
                print "\t%-10s : %s"%(key,val)
                    
            print ""
            
            import devicedb
            import postgresops
            devicedb.connect()
            devdefs = {}
            if devicedb.connected():
                postgresops.check_evil(name)
                devices = devicedb.get_devices(where="source_name='%s'"%name,orderby='device_type ASC')
                for dev in devices:
                    
                    if ( not devdefs.has_key(dev.device_type) ):
                        devdefs[dev.device_type] = utils.read_device(dev.device_type)
                    
                    print "\t%s (%s):"%(dev.IDstr,devdefs[dev.device_type]['name'])
                        
                    for idx in range(len(dev.source_ids)):
                        id = dev.source_ids[idx]
                        if ( idx < len(dev.feed_names) ):
                            print "\t\t%20s : %s"%(dev.feed_names[idx],id)
                        else:
                            print "\t\t%20s : %s"%('???',id)
                        
                    print ""
                
            
            
elif sys.argv[1] == 'fetch':
    import pycurl
    
    last_update = 0;
    def progress_cb(download_tot, download_done, upload_tot, upload_done):
        global last_update
        if ( time.time() - last_update < 1):
            return
        
        last_update = time.time()
        if ( download_tot == 0 ):
            utils.log_prog(1,1,"FETCHING URL","%.2f MB"%(download_done/1e6))
        else:
            utils.log_prog(1,1,"FETCHING URL","%.2f%%"%(100.*float(download_done)/download_tot))
    
    fromtime = datetime.now() - timedelta(weeks=1)
    totime = datetime.now()
    
    
    try:
        i = sys.argv.index('--from')
        try:
            fromtime = utils.str_to_date(sys.argv[i+1])
        except ValueError, msg:
            print "Bad from time: "+str(msg)
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:pass
    
    try:
        i = sys.argv.index('--to')
        try:
            totime = utils.str_to_date(sys.argv[i+1])
        except ValueError, msg:
            print "Bad to time: "+str(msg)
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:pass
    
    try:
        i = sys.argv.index('--plot')
        plotfile = sys.argv[i+1]
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:
        plotfile = None
    
    try:
        i = sys.argv.index('--title')
        plottitle = sys.argv[i+1]
        sys.argv = sys.argv[0:i] + sys.argv[i+2:]
    except ValueError:
        plottitle = None
    
    if len(sys.argv) != 5:
        print "Not enough arguments"
    
    source_name = sys.argv[2]
    fmap = config.read_struct(config.map['global']['source_dir']+'/'+source_name+'.src')
    if fmap == None:
        print "Couldn't load source description file"
        sys.exit(1);
            
    devid = sys.argv[3]
    outfile = sys.argv[4]
    
    #set up some defaults
    def setdef(name,val):
        if not fmap.has_key(name): fmap[name] = val;
    
    setdef('intr','1')
    setdef('type','TIMESERIES')
    
    curl = pycurl.Curl()
    do_url_fetch = False
    do_cmd_run = False
            
    # SET UP URL & HEADERS   
    if (fmap['driver'] == 'SMAP') :
        intr = float(fmap['intr'])
        url = fmap['url']+'api/data/uuid/%s?starttime=%d&endtime=%d&format=csv&tags=&'%(devid,intr * utils.date_to_unix(fromtime),intr * utils.date_to_unix(totime))
        do_url_fetch = True
    elif (fmap['driver'] == 'COSM'):
        url = 'http://api.cosm.com/v2/feeds/'+devid+'.csv'
        print "Setting COSM API key: %s"%fmap['apikey']
        curl.setopt(curl.HTTPHEADER, ['X-ApiKey: %s'%fmap['apikey']])
        do_url_fetch = True
    elif (fmap['driver'] == 'CSV'):
        intr = float(fmap['intr'])
        cmd = "/usr/bin/perl -w %s %d %d %s %s"%(config.map['global']['bin_dir']+'/csv_merge.pl',intr*utils.date_to_unix(fromtime),intr*utils.date_to_unix(totime),outfile,devid)
        do_cmd_run = True
    elif (fmap['driver'] == 'YFIND'):
        import json, tempfile
        cache_dir = config.map['global']['data_dir']+'/'+source_name+'_cache'
        try:
            os.makedirs(cache_dir,0700)
        except:pass
        
        curdate = fromtime
        datfout = tempfile.NamedTemporaryFile()
        if ( devid == 'ALL' ):
            datfout.write("#yFind Localization System Data\n#Source: %s\n#All MAC Addresses\n"%source_name)
            datfout.write("#%9s, %16s, %5s, %10s, %10s\n"%('ts','MAC Addr','Floor','X','Y'))
        else:
            datfout.write("#yFind Localization System Data\n#Source: %s\n#MAC Address: %s\n"%(source_name,devid))
            datfout.write("#%9s, %5s, %10s, %10s\n"%('ts','Floor','X','Y'))
        
        while curdate.day <= totime.day or curdate.month < totime.month or curdate.year < totime.year:
            datestr = "%04d-%02d-%02d"%(curdate.year,curdate.month,curdate.day)
            url = fmap['url'] + 'api/%s/footfalls.json?api_key=%s&date=%s'%(fmap['venueID'],fmap['apikey'],datestr)
            cache_fname = cache_dir + '/yfind_footfall_' + datestr + '.csv';
            if os.path.exists(cache_fname) and datetime.utcnow().date() != curdate.date():
                print "Date %s already exists in cache, skip fetch"%datestr
            else:
                fout = tempfile.TemporaryFile();
                curl.setopt(curl.NOPROGRESS, 0)
                curl.setopt(curl.PROGRESSFUNCTION, progress_cb)
                print "Fetching URL: %s"%url
                curl.setopt(curl.URL, url)
                curl.setopt(curl.WRITEFUNCTION, fout.write)
                curl.perform()
                fout.seek(0)
                js = json.load(fout)                
                fout.close()
                
                fout = open(cache_fname,'w');
                fout.write("#%9s, %16s, %5s, %10s, %10s\n"%('ts','MAC Addr','Floor','X','Y'))
                for j in js:
                    ts = datetime.strptime(j['timestamp'][0:-6], "%Y-%m-%dT%H:%M:%S")
                    tzoffset = int(j['timestamp'][-6:-3])
                    ts += timedelta(hours=tzoffset)
                    datline = "%10d, %16s, %5d, %10.2f, %10.2f\n"%(utils.date_to_unix(ts), j['mac'], j['floor_number'], j['x'], j['y']);
                    fout.write(datline);
                fout.close();
                
            curdate += timedelta(days=1);
            
            fin = open(cache_fname, 'r')
            ftime = utils.date_to_unix(fromtime)
            ttime = utils.date_to_unix(totime)
            for l in fin:
                if ',' in l and not l[0] == '#':
                    pts = l.split(',')
                    ts = int(pts[0].strip())
                    if ts >= ftime and ts <= ttime:
                        if devid == "ALL":
                            datfout.write(l);
                        elif pts[1].strip() == devid:
                            datfout.write("%s,%s,%s,%s"%(pts[0],pts[2],pts[3],pts[4]))
                        
                    
            fin.close()
        
        datfout.delete = False
        datfout.close()
        shutil.move(datfout.name, outfile);
        
    else:
        print "No driver for %s"%fmap['driver']
        
    if do_url_fetch:
        fout = open(outfile,'w')
        curl.setopt(curl.NOPROGRESS, 0)
        curl.setopt(curl.PROGRESSFUNCTION, progress_cb)
        print "Fetching from %s to %s"%(utils.date_to_str(fromtime),utils.date_to_str(totime))
        print "URL: %s"%url
        curl.setopt(curl.URL, url)
        curl.setopt(curl.WRITEDATA, fout)
        curl.perform()
        fout.close()
        
    if do_cmd_run:
        import subprocess
        print "Calling "+cmd
        ret = subprocess.call(cmd.split(' '))
        if ( ret != 0 ):
            print "Error in command"
            os.remove(outfile)
            sys.exit(1)
    
    # POST-ANALYSIS & PROCESSING
    if (fmap['driver'] == 'SMAP') :
        fin = open(outfile,'r')
        if ( 'Error' in fin.read(128)):
            print "Error fetching from SMAP. Did you provide a valid UUID?"
            os.remove(outfile)
            sys.exit(1)
        fin.close()
    elif (fmap['driver'] == 'COSM'):
        fin = open(outfile,'r')
        if ( 'You do not have permission to access' in fin.read(64)):
            print "Error: No permission to access COSM resource (bad API key?)"
            os.remove(outfile)
            sys.exit(1)
        fin.close()
        
    if plotfile:
        import shlex,subprocess
        if not plottitle:
            plottitle = "Source:%s ID:%s"%(sys.argv[2],devid)
            
        cmdline = str(config.map['web']['plotcsvcmd'] + '-csvin %s -pngout %s -title "%s"'%(outfile,plotfile,plottitle));
        sys.exit(subprocess.call(shlex.split(cmdline)))
        
    sys.exit(0)