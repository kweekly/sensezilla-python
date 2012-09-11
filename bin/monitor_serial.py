#!/usr/bin/python

import sys
import serial
import time

if len(sys.argv) < 2:
    print "Usage: monitor_serial.py <serial port> [speed]"
    sys.exit(1);
    
sport = sys.argv[1]
if len(sys.argv) >= 3:
    speed = int(sys.argv[2])
else:
    speed = 9600;
    
ser = serial.Serial(sport, speed, timeout=.01)
timeout = 0.1
last_byte = 0;
pack_print = False
while True:
    b = ser.read();
    if len(b) > 0:
        sys.stdout.write( ''.join(['%02X'%ord(c) for c in b]))
        pack_print = True
        last_byte = time.time()
    
    if pack_print and time.time() > last_byte + timeout:
        print
        pack_print = False
        
    time.sleep(0.01)