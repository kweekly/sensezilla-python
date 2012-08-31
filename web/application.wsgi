import os
import sys
import time
import psutil
import cgi 
                
from jinja2 import * 
 
sys.path.append(os.path.dirname(__file__))         
     
def application(environ, start_response):
    global config, mod_exec_IF
    
    if 'SENSEZILLA_DIR' not in os.environ:
        if 'SENSEZILLA_DIR' not in environ:
            print "Note: SENSEZILLA_DIR not provided. Assuming "+environ['DOCUMENT_ROOT']+"/.."
            environ['SENSEZILLA_DIR'] = environ['DOCUMENT_ROOT']+"/.."
        os.environ['SENSEZILLA_DIR'] = environ['SENSEZILLA_DIR']
        
        sys.path.insert(0,environ['SENSEZILLA_DIR']+"/includes");
    import config
    from mod_exec import mod_exec_IF

    req = environ['PATH_INFO']         
    try:
        if ( req == '/index'):
            from index import do_index 
            return do_index(environ,start_response)    
        elif (req == '/admin'):
            from admin import do_admin
            return do_admin(environ,start_response)
        elif (req == '/tasks'):
            from tasks import do_tasks
            return do_tasks(environ,start_response)
        elif (req == '/showlog'): 
            from showlog import do_showlog
            return do_showlog(environ,start_response)
        elif (req == '/flows'):
            from flows import do_flows
            return do_flows(environ,start_response)
        elif (req == '/showplot'):
            from showplot import do_showplot
            return do_showplot(environ,start_response)
        elif (req.startswith("/locationbuilder")):
            from locationbuilder import do_locationbuilder
            return do_locationbuilder(req,environ,start_response)
        elif (req.startswith("/flowbuilder")):
            from flowbuilder import do_flowbuilder
            return do_flowbuilder(req,environ,start_response)
        else:
            start_response('301 Redirect', [('Location', '/index')]);
            return []
    except Exception, e:
        import traceback 
        start_response('500 Error',[('Content-Type','text/html')])
        return ["<pre>",traceback.format_exc(),"</pre>"]
    

    
    


