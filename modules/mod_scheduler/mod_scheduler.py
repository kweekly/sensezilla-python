# -*- coding: utf-8 -*-
import os,sys, re
import time
# Gen3 common modules
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import unixIPC

import google.protobuf

import scheduledb

scheduledb.connect()
scheduledb.initdb()
scheduledb.add_task(scheduledb.Task())