import sys

import numpy as np
from plotly.offline import plot
import plotly
import plotly.graph_objs as go
import datetime
import time

import babeltrace.reader

import tracer

import os

noProd = False

def timestampToDate(timestamp) :
    return  datetime.datetime.fromtimestamp(timestamp / 1e9).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    #help(plotly.offline.plot)
    if len(sys.argv) != 2:
        msg = 'Usage: python {} TRACEPATH'.format(sys.argv[0])
        raise ValueError(msg)
    
    sessions = tracer.getSessions(sys.argv[1])
    
    contVal = True;
    
    while contVal :
        i = 1
        for ses in sessions :
            errorString = ''
            if (ses[0]['exitCode'] != 0) :
                errorString = 'NOT COMPLETED'
            
            print( str(i) + " : " + timestampToDate(ses[0]['timestamp']) + " - "+ timestampToDate(ses[1])
                  + " : {:.1f}s ".format((ses[1] - ses[0]['timestamp']) / 1000000000) + errorString)
            if 'startPipelineSize' in ses[0] :
                 print( "      Start Pipeline size\t: " + str(ses[0]['startPipelineSize']))
            print( "      Max Pipeline size \t: " + str(ses[0]['maxPipelineSize']))
            print( "      Interest lifetime \t: " + str(ses[0]['interestLifetime']))
            print( "      Max retries       \t: " + str(ses[0]['maxRetries']))
            print( "      Must be fresh     \t: " + str(ses[0]['mustBeFresh']))
            print( "      Exit code         \t: " + str(ses[0]['exitCode']))
            print()
            ses[0]['id'] = i
            i += 1
            
    
        
    #try :
        if len(sessions) > 1 :
            sessionNo = int(input('Insert session number (0 to select all): '))
        else :
            sessionNo = 1
            contVal = False
        if sessionNo > len(sessions) :
            print("ERROR: no session with specified number")
        else :
            if (sessionNo == 0) :
                global_start_time = time.time()
                for i in range (0, len(sessions)) :
                    start_time = time.time()
                    print ("Running with session " + str(i + 1) + "...")
                    tracer.chunksStatistics(sys.argv[1], sessions[i][0]['timestamp'], sessions[i][1], sessions[i], noProd)
                    elapsed_time = time.time() - start_time
                    print ("Elapsed time: " + str(int(elapsed_time/60)) + ":" + str(int(elapsed_time%60)))
                contVal = False
                global_elapsed_time = time.time() - global_start_time
                print ("Total elapsed time: " + str(int(global_elapsed_time/60)) + ":" + str(int(global_elapsed_time%60)))
            else :
                start_time = time.time()
                print ("Running with session " + str(sessionNo) + "...")
                tracer.chunksStatistics(sys.argv[1], sessions[sessionNo - 1][0]['timestamp'], sessions[sessionNo - 1][1], sessions[sessionNo - 1], noProd)
                elapsed_time = time.time() - start_time
                print ("Elapsed time: " + str(int(elapsed_time/60)) + ":" + str(int(elapsed_time%60)))
    #except ValueError :
        #print("ERROR: Insert a number " )
