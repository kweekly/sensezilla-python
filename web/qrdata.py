# -*- coding: utf-8 -*-
import os
import sys
import time
import psutil
import cgi

from jinja2 import * 
import httplib

CODES = {
    "d00001" : "818a5336-0f4d-5088-a1a9-14e4e4410fa2",
    "d00002" : "ff250610-ad0f-5055-a726-35733494b6e5",
    "d00003" : "fbc2a542-3719-5046-aebe-f0c68e41e231",
    "d00004" : "a586d399-cdfb-5a8a-a4cd-f3642823b4ee",
    #"d00005" : "d5a8842f-e5fb-5e10-bfe1-a340c0cb7a24",
    #"d00006" : "b79ce629-9393-55d7-8862-762c2bcc2cb3"
 };
    

def do_qrdata(environ, start_response):
    start_response('200 OK',[('Content-Type','text/plain')])
    con = httplib.HTTPConnection("sensezilla.berkeley.edu");
    resp = []
    for code,uid in CODES.iteritems():
        con.request("GET","/backend/api/prev/uuid/%s?starttime=%d&format=csv&tags=&"%(uid,int(1000*time.time())));
        bmsresp = con.getresponse()
        datlines = bmsresp.read().splitlines()
        tm = 0;
        val = -1;
        for dl in datlines:
            
            if len(dl) > 0 and dl[0] != '#' and ',' in dl:
                tm,val = dl.split(',')
                break
                
        resp.append("%s:%.5f\n"%(code,float(val)));
    con.close();
    return resp;