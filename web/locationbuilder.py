import os
import sys
import time
import psutil
import cgi 

from jinja2 import * 

def gen_loc_option_list(parent, level, listgen, idstop, idselect):
    return gen_option_list(parent, level, listgen, idstop, idselect,"LOCATION")

def gen_option_list(parent, level, listgen, idstop, idselect,key):
    import devicedb
    metadata = devicedb.get_devicemetas(where="key='%s' and parent=%d"%(key,parent), orderby="value ASC")
    for met in metadata:
        if idselect == met.ID:
            seltex = 'selected="selected"'
        else:
            seltex = ''
              
        if (met.ID != idstop):
            if level > 0:
                listgen += "<option value=%d"%met.ID+" %s>"%seltex+"-"*level+" "+met.value+"</option>\n";
            else:
                listgen += "<option value=%d"%met.ID+" %s>"%seltex+"<b>"+met.value+"</b></option>\n";
            listgen = gen_option_list(met.ID,level+1,listgen,idstop,idselect,key);
    return listgen
        

def do_locationbuilder(req,environ,start_response):
    import config 
    import devicedb
    import postgresops
    devicedb.connect()
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    if ( req == '/locationbuilder' or req == '/locationbuilder/' ):
        req = '/locationbuilder/index'
    
    if '?' in req:
        tempname = req[0:req.find('?')]
    else:
        tempname = req
    
    pagename = tempname[tempname.rfind("/")+1:]
    
    try:
        template = env.get_template(tempname+'.html')
    except TemplateNotFound:
        start_response('404 Not Found',[])
        return [];
        
    start_response('200 OK',[('Content-Type','text/html')])
    
    d = cgi.parse_qs(environ['QUERY_STRING'])
    
    if pagename=='metalinks':   
        key = d['type'][0].upper()
        main = d['main'][0].lower()
        postgresops.check_evil(key)
        postgresops.check_evil(main, ['/'])
        metadata = devicedb.get_devicemetas(where="key='%s' and parent=0"%key, orderby="value ASC")
        linkgen = ''
        def radd(parent,level, linkgen):
           newmetas = devicedb.get_devicemetas(where="key='%s' and parent=%d"%(key,parent), orderby="value ASC")
           for met in newmetas: 
               linkgen += "-"*level+" "+"<a target=main href='/locationbuilder/%s?id=%d&type=%s'>"%(main,met.ID,key)+met.value+"</a> ["+\
                                        "<a target=main href='/locationbuilder/%s?id=new&parent=%d&type=%s'"%(main,met.ID,key)+">+</a>]<br>";
               linkgen = radd(met.ID,level+1,linkgen);
           return linkgen  
             
               
        for met in metadata:
             linkgen += "<h3><a target=main href='/locationbuilder/%s?id=%d&type=%s'>"%(main,met.ID,key)+met.value+"</a> [<a target=main href='/locationbuilder/%s?id=new&parent=%d&type=%s'"%(main,met.ID,key)+">+</a>]</h3>\n"
             linkgen = radd(met.ID,1,linkgen)
             
        linkgen += "<h3><a target=main href='/locationbuilder/%s?id=new&parent=0&type=%s'>New %s...</a></h3>"%(main,key,key.lower())
        
        return [str(template.render( linkgen = linkgen ))]
    
    elif pagename=='devlinks':
        if 'categorize' in d:
            categorize = d['categorize'][0]
        else:
            categorize = 'type'
            
        devices = {};
        if categorize == 'type':
            devs = devicedb.get_devices(orderby='idstr ASC')
            for dev in devs:
                if ( devices.has_key(dev.device_type )):
                    devices[dev.device_type].append(dev);
                else:
                    devices[dev.device_type] = [dev]
        elif categorize == 'location':
            toplevels = devicedb.get_devicemetas(where="key='LOCATION' and parent=0")
            for top in toplevels:
                devices[top.value] = devicedb.find_devices_under(top);
    
        return [str(template.render( categorize = categorize, devices = devices ))]
    
    elif pagename=='showmeta':
        if 'action' in d and d['action'][0] == 'delete':
            def rdelete(id):
                metadata = devicedb.get_devicemetas(where="parent=%d"%id)
                for met in metadata:
                    rdelete(met.ID);
                devicedb.delete_devicemeta(id)
              
            rdelete(int(d['id'][0]))
            
            return ['<html><script>window.parent.frames["links"].document.location.reload();\nwindow.location="/locationbuilder/start";</script></html>'];

        key = d['type'][0].upper()
        postgresops.check_evil(key)

        if 'parent' in d and d['parent'][0] != '0': 
            parid = int(d['parent'][0]);
            parentmeta = devicedb.get_devicemetas(where="id=%d"%parid,limit=1)[0];
        else:
            parentmeta = None 
                    
        if d['id'][0] == 'new':
            meta = devicedb.new_devicemeta()
            meta.key = key;
            meta.value= "New "+key.lower()
            if parentmeta != None:
                meta.parent = parentmeta.ID
            else:
                meta.parent = 0
                
            devicedb.insert_devicemeta(meta)
        else:
            meta = devicedb.get_devicemetas(where="key='%s' and id=%d"%(key,int(d['id'][0])))[0]

        if 'action' in d and d['action'][0] == 'edit':
            post = cgi.FieldStorage(fp=environ['wsgi.input'],environ=environ,keep_blank_values=True);
            meta.value = post['value'].value
            if 'noparent' in post:
                meta.parent = 0
            elif 'parent' in post and meta.ID != int(post['parent'].value):
                if meta.parent != int(post['parent'].value):
                    parentmeta = devicedb.get_devicemetas(where="id=%d"%int(post['parent'].value),limit=1)[0]
                    
                meta.parent = int(post['parent'].value)
                 
            devicedb.update_devicemeta(meta)
            
        listgen = gen_option_list(0,0,'',meta.ID,meta.parent,key)
                    
        return [str(template.render(
                                    key=key,
                                    listgen=listgen,
                                    meta = meta 
            ))]
    elif pagename=='showloc':
        if 'action' in d and d['action'][0] == 'delete':
            def rdelete(id):
                metadata = devicedb.get_devicemetas(where="parent=%d"%id)
                for met in metadata:
                    rdelete(met.ID);
                devicedb.delete_devicemeta(id)
              
            rdelete(int(d['id'][0]))
            
            return ['<html><script>window.parent.frames["links"].document.location.reload();\nwindow.location="/locationbuilder/start";</script></html>'];
                       
        if 'parent' in d and d['parent'][0] != '0': 
            parid = int(d['parent'][0]);
            parentloc = devicedb.get_devicemetas(where="id=%d"%parid,limit=1)[0];
        else:
            parentloc = None
            
        if d['id'][0] == 'new':
            loc = devicedb.new_devicemeta()
            loc.key = "LOCATION"
            loc.value = "New Location"
            if parentloc != None:
                loc.parent = parentloc.ID
            else:
                loc.parent = 0
                
            devicedb.insert_devicemeta(loc);
        else:
            loc = devicedb.get_devicemetas(where="id=%d"%int(d['id'][0]),limit=1)[0];
        
        if 'action' in d and d['action'][0] == 'edit':
            post = cgi.FieldStorage(fp=environ['wsgi.input'],environ=environ,keep_blank_values=True);
            loc.value = post['value'].value
            if 'noparent' in post:
                loc.parent = 0
            elif 'parent' in post and loc.ID != int(post['parent'].value):
                if loc.parent != int(post['parent'].value):
                    parentloc = devicedb.get_devicemetas(where="id=%d"%int(post['parent'].value),limit=1)[0]
                    
                loc.parent = int(post['parent'].value)
                 
            devicedb.update_devicemeta(loc)
            
            if '.svg' in post['svgfile'].value :
                svgmeta = devicedb.get_devicemetas(where="key='SVGFILE' and parent=%d"%loc.ID,limit=1)
                if ( len(svgmeta) > 0 ):
                    svgmeta[0].value = post['svgfile'].value
                    devicedb.update_devicemeta(svgmeta[0])
                else:
                    svgmeta = devicedb.new_devicemeta()
                    svgmeta.key = 'SVGFILE'
                    svgmeta.value = post['svgfile'].value
                    svgmeta.parent = loc.ID
                    devicedb.insert_devicemeta(svgmeta)
                    
            svgmeta = devicedb.get_devicemetas(where="key='SVGPOSITION' and parent=%d"%loc.ID,limit=1)
            posstr = "%.2f,%.2f,%.2f,%.2f"%(float(post['x1'].value),float(post['y1'].value),float(post['x2'].value),float(post['y2'].value))
            if ( len(svgmeta) > 0 ):
                svgmeta[0].value = posstr
                devicedb.update_devicemeta(svgmeta[0])
            else:
                svgmeta = devicedb.new_devicemeta()
                svgmeta.key = 'SVGPOSITION'
                svgmeta.value = posstr
                svgmeta.parent = loc.ID
                devicedb.insert_devicemeta(svgmeta)
                                
        svgmeta = devicedb.get_devicemetas(where="key='SVGFILE' and parent=%d"%loc.ID,limit=1)
        svgpos = {}
        svgheight = 300
        svgwidth = 200
        if len(svgmeta) > 0:
            svgfile = svgmeta[0].value
            svgmeta = devicedb.get_devicemetas(where="key='SVGPOSITION' and parent=%d"%loc.ID,limit=1)
            if (len(svgmeta) > 0):
                pts = svgmeta[0].value.split(',')
                svgpos['x1'] = float(pts[0]);
                svgpos['y1'] = float(pts[1]);
                svgpos['x2'] = float(pts[2]);
                svgpos['y2'] = float(pts[3]);
            else:
                svgpos['x1'] = 0;
                svgpos['y1'] = 0;
                svgpos['x2'] = 0; 
                svgpos['y2'] = 0;
                
            if '..' in svgfile:
                svgdata = '<br>\nSECURITY VIOLATION'
            else:        
                try:
                    fin = open(config.map['web']['mapdir']+'/'+svgfile,'r');
                    buf = ''
                    state = 0;
                    while True:
                        lbuf = fin.read(128);
                        buf += lbuf
                        if lbuf == '' or lbuf == None:
                            state = 9;
                            break;
                        if state == 0 and '<svg' in buf:
                            buf = buf[buf.find('<svg')+4:]
                            state = 1;
                        if state == 1:
                            if 'width="' in buf:
                                idx = buf.find('width="')+7;
                                svgwidth = float(buf[idx:buf.find('"',idx)])
                                
                            if 'height="' in buf:
                                idx = buf.find('height="')+8;
                                svgheight = float(buf[idx:buf.find('"',idx)]) 
                                
                            if '>' in buf:
                                buf = buf[buf.find('>')+1:] 
                                state = 2;
                        elif state == 2 and '</svg>' in buf:
                            buf = buf[:buf.find('</svg>')]
                            break;
                    svgdata = buf;
                    fin.close();
                except Exception,e:
                    svgdata = '<br>\nCannot read SVG file: '+str(e)
        else:
            svgfile = 'Not Specified'
            svgdata = ''
            svgpos['x1'] = 0;
            svgpos['y1'] = 0;
            svgpos['x2'] = 0;
            svgpos['y2'] = 0;
                
            
        listgen = gen_loc_option_list(0,0,'',loc.ID,loc.parent)

            
              
        return [str(template.render(loc=loc,
                                    listgen=listgen,
                                    svgfile=svgfile,
                                    svgdata=svgdata, 
                                    svgpos=svgpos,
                                    svgwidth=svgwidth,
                                    svgheight=svgheight))]
    elif pagename=='showdev':
        import utils

        if 'action' in d and d['action'][0] == 'delete':
            devid = int(d['id'][0])
            metas = devicedb.get_devicemetas(where='%d=any(devices)'%devid)
            for met in metas:
                met.devices.remove(devid)
                devicedb.update_devicemeta(met)
            
            devicedb.delete_device(devid)
            
            return ['<html><script>window.parent.frames["links"].document.location.reload();\nwindow.location="/locationbuilder/start";</script></html>'];
         
        
        if d['id'][0] == 'new':
            dev = devicedb.new_device()
            dev.IDstr = "Undefined"
            dev.device_type = "test"
            dev.source_name = "csv"
            devicedb.insert_device(dev)
        else:
            dev = devicedb.get_devices(where="id=%d"%(int(d['id'][0])),limit=1)[0]

        devdeflistfiles = utils.list_devicedefs()
        devdeflist=[]
        for devdeffile in devdeflistfiles:
            struc = utils.read_device(devdeffile)
            if ( devdeffile == dev.device_type ):
                devdef = struc
            devdeflist.append(struc['name']);
                    
        if 'action' in d and d['action'][0] == 'edit':
            post = cgi.FieldStorage(fp=environ['wsgi.input'],environ=environ,keep_blank_values=True);
            dev.IDstr = post['IDstr'].value
            dev.source_ids = []
            for i in range(len(devdef['feeds'])):
                dev.source_ids.append(post['feed%d'%i].value)
            
            if (post['devdef'].value != dev.device_type):
                dev.device_type = post['devdef'].value
                devdef = utils.read_device(dev.device_type)
                
            dev.source_name = post['source'].value
            
            curlocs = devicedb.get_devicemetas(where="key='LOCATION' and %d=any(devices)"%dev.ID)
            
            
            if ('location' not in post or 'noloc' in post):
                noloc = True
            else:
                noloc = False
            
            if ( len(curlocs) > 1 or (len(curlocs) == 1 and (noloc or curlocs[0].ID != post['location'].value))):
                for loc in curlocs:
                    loc.devices.remove(dev.ID)
                    devicedb.update_devicemeta(loc);
                
            if ( 'noloc' not in post ):
                loc = devicedb.get_devicemetas(where="id=%d"%(int(post['location'].value)),limit=1)
                loc[0].devices.append(dev.ID)
                devicedb.update_devicemeta(loc[0])
                
            for i in range(len(devdef['feeds'])):
                if ( 'plugload%d'%i in post ):
                    plugl = devicedb.get_devicemetas(where="key='PLUGLOAD%d' and %d=any(devices)"%(i,dev.ID),limit=1)
                    if len(plugl)==0 and post['plugload%d'%i].value != '0':
                        plugl = devicedb.new_devicemeta()
                        plugl.key = "PLUGLOAD%d"%i
                        plugl.value = ''
                        plugl.devices = [dev.ID]
                        plugl.parent = int(post['plugload%d'%i].value)
                        devicedb.insert_devicemeta(plugl)
                    elif len(plugl)==1 and plugl[0].parent != int(post['plugload%d'%i].value):
                        if post['plugload%d'%i].value == '0':
                            devicedb.delete_devicemeta(plugl[0].ID)
                        else:
                            plugl[0].parent = int(post['plugload%d'%i].value)
                            devicedb.update_devicemeta(plugl[0])
          
            curuser = devicedb.get_devicemetas(where="key='USER' and %d=any(devices)"%(dev.ID))
            found = False
            for c in curuser:
                if ( c.ID != int(post['user'].value) ):
                    c.devices.remove(dev.ID)
                    devicedb.update_devicemeta(c)
                else:
                    found = True
            
            if not found and post['user'].value != '0':
                curuser = devicedb.get_devicemetas(where="key='USER' and id=%d"%int(post['user'].value))
                curuser[0].devices.append(dev.ID)
                devicedb.update_devicemeta(curuser[0])
            
            devicedb.update_device(dev)

        
        if not devdef.has_key('svgfile'):
            devdef['svgfile'] = config.map['global']['device_dir']+'/unknown.svg';
            
        fin = open(devdef['svgfile'],'r')
        svgdata = fin.read()
        fin.close()
                
        sourcelist = utils.list_sources()
        sourcedef = utils.read_source(dev.source_name);
        
        curloc = devicedb.get_devicemetas(where="key='LOCATION' and %d=any(devices)"%dev.ID,limit=1)
        if len(curloc) == 0:
            locoptions = gen_loc_option_list(0, 0, '', 0, 0)
            noloc = True
        else:
            locoptions = gen_loc_option_list(0,0,'',0,curloc[0].ID)
            noloc = False
        
        
        loadsellists = [];
        curloadsels = []
        for i in range(len(devdef['feeds'])):
            plugs = devicedb.get_devicemetas(where="key='PLUGLOAD%d' and %d=any(devices)"%(i,dev.ID),limit=1)
            if len(plugs)==1:
                curloadsels.append(plugs[0].parent);
            else:
                curloadsels.append(0)

            loadsellists.append(gen_option_list(0,0,'',0,curloadsels[-1],'PLUGLOAD'))
            
        userlist = []
        def rgenusers(id,userlist):
            metas = devicedb.get_devicemetas(where="key='USER' and parent=%d"%id,orderby='value ASC')
            if ( len(metas) == 0 ):
                u = devicedb.get_devicemetas(where="id=%d"%id)
                userlist.append(u[0])
                if dev.ID in u[0].devices:
                    return u[0].ID
                return 0
            else:
                retval = 0
                for u in metas:
                    id = rgenusers(u.ID,userlist)
                    if id != 0:
                        retval = id
                return retval
        
        curuser = rgenusers(0,userlist)
            
        sourcedef['ID_string_format'] = cgi.escape( sourcedef['ID_string_format'] )
        devdef['ID_string_format'] = cgi.escape( devdef['ID_string_format'] )
        return [str(template.render(dev=dev,
                                    devdef=devdef,
                                    devdeflist=devdeflist,
                                    devdeflistfiles=devdeflistfiles,
                                    sourcelist=sourcelist,
                                    sourcedef=sourcedef,
                                    locoptions=locoptions,
                                    noloc=noloc,
                                    loadsellists=loadsellists,
                                    curloadsels=curloadsels,
                                    userlist=userlist,
                                    curuser=curuser,
                                    svgdata=svgdata))]
    
    else:
        return [str(template.render())]
