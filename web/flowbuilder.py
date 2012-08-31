import os
import sys
import time
import psutil
import cgi 

from jinja2 import * 

def do_flowbuilder(req,environ,start_response):
    import config 
    import devicedb
    import postgresops
    devicedb.connect()
    
    env = Environment(loader=FileSystemLoader(environ['DOCUMENT_ROOT']));
    if ( req == '/flowbuilder' or req == '/flowbuilder/' ):
        req = '/flowbuilder/index'
    
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
    
    return [str(template.render())]
    