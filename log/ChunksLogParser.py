import sys
import babeltrace.reader
import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
import datetime

import tracer

import os

def timestampToDate(timestamp) :
    return  datetime.datetime.fromtimestamp(ses[0]['timestamp'] / 1e9).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        msg = 'Usage: python {} TRACEPATH'.format(sys.argv[0])
        raise ValueError(msg)
    
    sessions = tracer.getSessions(sys.argv[1])
    i = 0
    for ses in sessions : 
        print( str(i) + " : " + timestampToDate(ses[0]['timestamp']))
        print( "      Max Pipeline size\t: " + str(ses[0]['maxPipelineSize']))
        print( "      Interest lifetime\t: " + str(ses[0]['interestLifetime']))
        print( "      Max retries\t: " + str(ses[0]['maxRetries']))
        print( "      Must be fresh\t: " + str(ses[0]['mustBeFresh']))
        print()
        i += 1
        
    try:
        sessionNo = int(input('Insert session number: '))
        if sessionNo >= len(sessions) :
            print("ERROR: no session with specified number")
        else :
            tracer.chunksStatistics(sys.argv[1], sessions[sessionNo][0]['timestamp'], sessions[sessionNo][1])
    except ValueError :
        print("ERROR: Insert a number")
