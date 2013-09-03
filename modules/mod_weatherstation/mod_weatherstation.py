#!/usr/bin/python

import os,sys, re
import time
from datetime import datetime, timedelta
# Gen3 common modules
if 'SENSEZILLA_DIR' not in os.environ:
    print "Note: SENSEZILLA_DIR not provided. Assuming ../../"
    os.environ['SENSEZILLA_DIR'] = "../.."

sys.path.insert(0,os.environ['SENSEZILLA_DIR']+"/includes");
import config
import utils
import unixIPC
import struct
import serial

import socket
import traceback

SERIAL_PORTS = config.map['mod_weatherstation']['serial_ports'];

## Setup and open the serial port connection, import the time and socket modules
## for later use
def connect_serial():
    global serbuf
    import glob
    serbuf = ''
    sports = []
    for spname in SERIAL_PORTS:
        sports += glob.glob(spname)
    
    if len(sports) <= 0:
        if print_errors:
            print "Error: No available serial ports"
        ser = None
        return
    elif len(sports) > 1:
        if print_errors:
            print "Warning: >1 serial port avaialable, using first"
    
    print "Opening serial port",sports[0]
    ser = serial.Serial(sports[0],int(config.map['mod_weatherstation']['serial_speed']),timeout=1)
    return ser
    
## Define the CRC table to be used in the CRC redundancy check
crc_table = [
0x0, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
0x1231, 0x210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
0x2462, 0x3443, 0x420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
0x3653, 0x2672, 0x1611, 0x630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
0x48c4, 0x58e5, 0x6886, 0x78a7, 0x840, 0x1861, 0x2802, 0x3823,
0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0xa50, 0x3a33, 0x2a12,
0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0xc60, 0x1c41,
0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0xe70,
0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
0x1080, 0xa1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
0x2b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
0x34e2, 0x24c3, 0x14a0, 0x481, 0x7466, 0x6447, 0x5424, 0x4405,
0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
0x26d3, 0x36f2, 0x691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x8e1, 0x3882, 0x28a3,
0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
0x4a75, 0x5a54, 0x6a37, 0x7a16, 0xaf1, 0x1ad0, 0x2ab3, 0x3a92,
0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0xcc1,
0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0xed1, 0x1ef0,
]


## This function gets the raw data from the console by sending the command
## LOOP 1, which returns one LOOP packet, 99 bytes long. It only writes this command if the console is assessed to be awake and working
def gethexdata():
    global ser, sock, serbuf
    ser.write("LOOP 1\n")
    time_stamp = time.time() ## The function gets the time of the readings over here since asking the time of the consoel would be inaccurate itself, as the console would take time to respond
    Data = ser.read(2048)## The incoming bytes are read from the buffer
    #print "RCV",utils.hexify(Data)
    serbuf += Data
    
    Data = ['%02x'% ord(b) for b in serbuf] ## The raw data bytes are converted into a list of hex strings
    testData = Data[1:] ## in order to run the CRC check the the first hex string the Acknowledge code (0x6) is removed from the Data
    b = accuracytest(testData) ## The accuracy test is run on the data and for the moment the result is just printed. 
    #print b ## Ideally once the CRC check works correctly I would like to include an if statement here which re-requests the data if the packet is assessed to be inaccurate
    Data = [Data, time_stamp] ## A list with the hex data and time stamp is assigned as the return
    return Data
    
## This function was used to find the 'LOO' in the Data packet so that we may extract the relevant data from the hex list based on its offset from these bytes 
def findstart(Data):
    x = 0
    while x < len(Data)-2:
        if (Data[x] == '4c') & (Data[x+1] == '4f') & (Data[x+2] == '4f'):
            return x
        x = x + 1
        
    return None
    
## There is not much too this function it just extracts the data we require from the data returned by the gethexdata function
def extractdata():
    global ser, sock, serbuf
    data = gethexdata()
    x = findstart(data[0])
    if not x:
        print "Start not found, throwing out",data[0]
        return None
        
    pressure = data[0][x+8] + data[0][x+7]
    in_temp = data[0][x+10]+data[0][x+9]
    in_humidity = data[0][x+11]
    out_temp = data[0][x+13]+data[0][x+12]
    wind_speed = data[0][x+14]
    wind_direct = data[0][x+17]+data[0][x+16]
    out_humidity = data[0][x+33]
    solar_radiation = data[0][x+45]+data[0][x+44]
    CRC = data[0][x+98]+data[0][x+97]
    if ( len(serbuf) > 98 ):
        serbuf = serbuf[97:]
    else:
        serbuf = ''
        
    time_stamp = data[1]
    newData = [pressure,in_temp,in_humidity,out_temp,wind_speed,wind_direct,out_humidity,solar_radiation,time_stamp]
    return newData

## The data extracted from the hexdata is now converted from hex-strings to integers and the raw values of temperature are divided by 10, while the raw value of
## humidity is divided by 1000 (based on the documentation)
def convertdata(data):
                newData = []
                for i in range (0,8):
                        newData.append(int(data[i],16))
                newData.append(data[-1])
                newData[1] = float(newData[1])/10
                newData[3] = float(newData[3])/10
                newData[0] = float(newData[0])/1000
                return newData
## The data obtained from convert data is simply placed in a string
def presentdata(newData):
        string = "driver/WeatherStation/device_id/VantagePro2_Berkeley/timestamp/{}/Pressure/{}/Indoor Temperature/{}/Indoor Humidity/{}/Outdoor Temperature/{}/Wind Speed/{}/Wind Direction/{}/Outdoor Humidity/{}/Solar Radiation/{}\n".format(newData[-1],newData[0],newData[1],newData[2],newData[3],newData[4],newData[5],newData[6],newData[7])
        return string
## This function is supposed to check whether there are any errors in the transmission of data from the console to the pc it returns True or False based on whether
## the data is accurate, the formula is used to calculate the CRC checksum has been obtained from the documentation
def accuracytest(hexlist):
        crc = 0## the checksum is preset to zero
        for info in hexlist:
                crc = shift8bit(crc) ^ (crc_table[ (crc >> 8) ^ int(info,16)])
                crc = crc & 0xFFFF
        if crc == 0:
                accurate = True
        else:
                accurate = False
        return accurate

def shift8bit(crc):
    string = hex(crc)
    newstring = string[4:] + '00'
    ncrc = int(newstring,16)
    return ncrc

def connecttoserver():
    try:
        s = socket.socket()
        host = config.map['global']['host']
        port = int(config.map['tv_relay']['port'])
        s.connect((host,port))
        return s
    except socket.error:
        return None


UPDATE_RATE = float(config.map['mod_weatherstation']['update_rate'])
                
## Call on the previously defined function and define a serial object ser
ser = connect_serial();
sock = connecttoserver();


while True:
    # assume serial port is always connected
    data = extractdata()
    if data:
        tlv_string = presentdata(convertdata(data))
    else: # no need for long sleep - taken care of by serial port
        time.sleep(0.01)
        continue
    
    if sock:
        try:
            sock.send(tlv_string);
        except socket.error:
            sock.close()
            sock = None
            time.sleep(0.5)
            continue
    else:
        time.sleep(0.5);
        sock = connecttoserver()
        continue; # attempt to reconnect
        
    time.sleep(UPDATE_RATE); # delay to allow other threads to run