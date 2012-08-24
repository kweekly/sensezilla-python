import os
import sys
import time
import psutil
import cgi 

from jinja2 import * 

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
    
    if pagename=='loclinks':   
        metadata = devicedb.get_devicemetas(where="key='LOCATION' and parent=0", orderby="value ASC")
        linkgen = ''
        def radd(parent,level, linkgen):
           newmetas = devicedb.get_devicemetas(where="key='LOCATION' and parent=%d"%parent, orderby="value ASC")
           for met in newmetas: 
               linkgen += "-"*level+" "+"<a target=main href='/locationbuilder/showloc?locid=%d'>"%met.ID+met.value+"</a> ["+\
                                        "<a target=main href='/locationbuilder/showloc?locid=new&parent=%d'"%met.ID+">+</a>]<br>";
               linkgen = radd(met.ID,level+1,linkgen);
           return linkgen  
             
               
        for met in metadata:
             linkgen += "<h3><a target=main href='/locationbuilder/showloc?locid=%d'>"%met.ID+met.value+"</a> [<a target=main href='/locationbuilder/showloc?locid=new&parent=%d'"%met.ID+">+</a>]</h3>\n"
             linkgen = radd(met.ID,1,linkgen)
             
        linkgen += "<h3><a target=main href='/locationbuilder/showloc?locid=new&parent=0'>New location...</a></h3>"
        
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
                    devices[dev.device_type].apppend(dev);
                else:
                    devices[dev.device_type] = [dev]
        elif categorize == 'location':
            toplevels = devicedb.get_devicemetas(where="key='LOCATION' and parent=0")
            for top in toplevels:
                devices[top.value] = devicedb.find_devices_under(top);
    
        return [str(template.render( categorize = categorize, devices = devices ))]
    
    elif pagename=='showloc':
        if 'action' in d and d['action'][0] == 'delete':
            def rdelete(id):
                metadata = devicedb.get_devicemetas(where="parent=%d"%id)
                for met in metadata:
                    rdelete(met.ID);
                devicedb.delete_devicemeta(id)
              
            rdelete(int(d['locid'][0]))
            
            return ['<html><script>window.parent.frames["links"].document.location.reload();\nwindow.location="/locationbuilder/start";</script></html>'];
                       
        if 'parent' in d and d['parent'][0] != '0': 
            parid = int(d['parent'][0]);
            parentloc = devicedb.get_devicemetas(where="id=%d"%parid,limit=1)[0];
        else:
            parentloc = None
            
        if d['locid'][0] == 'new':
            loc = devicedb.new_devicemeta()
            loc.key = "LOCATION"
            loc.value = "New Location"
            if parentloc != None:
                loc.parent = parentloc.ID
            else:
                loc.parent = 0
                
            devicedb.insert_devicemeta(loc);
        else:
            loc = devicedb.get_devicemetas(where="id=%d"%int(d['locid'][0]),limit=1)[0];
        
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
                        
        def radd(parent, level, listgen):
            metadata = devicedb.get_devicemetas(where="key='LOCATION' and parent=%d"%parent, orderby="value ASC")
            for met in metadata:
                if loc.parent == met.ID:
                    seltex = 'selected="selected"'
                else:
                    seltex = ''
                      
                if (met.ID != loc.ID):
                    if level > 0:
                        listgen += "<option value=%d"%met.ID+" %s>"%seltex+"-"*level+" "+met.value+"</option>\n";
                    else:
                        listgen += "<option value=%d"%met.ID+" %s>"%seltex+"<b>"+met.value+"</b></option>\n";
                    listgen = radd(met.ID,level+1,listgen);
            return listgen
        
        
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
                
            
        listgen = radd(0,0,'')

            
              
        return [str(template.render(loc=loc,
                                    listgen=listgen,
                                    svgfile=svgfile,
                                    svgdata=svgdata, 
                                    svgpos=svgpos,
                                    svgwidth=svgwidth,
                                    svgheight=svgheight))]
    elif pagename=='showdev':
        import utils
        if d['id'][0] == 'new':
            pass
        else:
            dev = devicedb.get_devices(where="id=%d"%(int(d['id'][0])),limit=1)[0]
            
            devdeflistfiles = utils.list_devicedefs()
            devdeflist=[]
            for devdeffile in devdeflistfiles:
                struc = utils.read_device(devdeffile)
                if ( devdeffile == dev.device_type ):
                    devdef = struc
                devdeflist.append(struc['name']);
            
            if not devdef.has_key('svgfile'):
                devdef['svgfile'] = config.map['global']['device_dir']+'/unknown.svg';
                
            fin = open(devdef['svgfile'],'r')
            svgdata = fin.read()
            fin.close()
            
            sourcelist = utils.list_sources()
            sourcedef = utils.read_source(dev.source_name);
            
            
        return [str(template.render(dev=dev,
                                    devdef=devdef,
                                    devdeflist=devdeflist,
                                    devdeflistfiles=devdeflistfiles,
                                    sourcelist=sourcelist,
                                    sourcedef=sourcedef,
                                    svgdata=svgdata))]
    
    else:
        return [str(template.render())]