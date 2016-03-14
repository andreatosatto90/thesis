import sys
import babeltrace.reader
import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
import copy

import os

def loadAllTraces(filepath):
    # a trace collection holds one to many traces
    col = babeltrace.TraceCollection()
    
    for subDir in os.listdir(filepath):
        if col.add_trace(filepath + subDir + '/64-bit/', 'ctf') is None:
            raise RuntimeError('Cannot add trace')
        
    return col

def startEventToList(event, exitCode = -1):
    dic = {}
    dic['timestamp'] = event.timestamp
    dic['startTime'] = event.datetime
    dic['maxPipelineSize'] = event['max_pipeline_size']
    dic['interestLifetime'] = event['interest_lifetime']
    dic['maxRetries'] = event['max_retries']
    dic['mustBeFresh'] = event['must_be_fresh']
    dic['exitCode'] = exitCode
    return dic

def getSessions(filepath):
    col = loadAllTraces(filepath)
    sessions = []

    lastStartEvent = None
    # get events per segment (chunks)
    for event in col.events:
        if event.name == 'chunksLog:cat_started' :
            if lastStartEvent != None:
                sessions.append([lastStartEvent, event.timestamp - 1])
                lastStartEvent = startEventToList(event)
            else :
                lastStartEvent = startEventToList(event)
        elif event.name == 'chunksLog:cat_stopped' :
           if lastStartEvent != None:
                lastStartEvent['exitCode'] = event['exit_code']
                sessions.append([lastStartEvent, event.timestamp])
                lastStartEvent = None
    
    if lastStartEvent != None :
        sessions.append([lastStartEvent, col.timestamp_end])
    
    return sessions

def chunksStatistics(filepath, start, stop, name = 'testNoName'):
    col = loadAllTraces(filepath)
    
    if start != -1 and stop != -1 :
        colEvents = col.events_timestamps(start, stop)
    else :
        colEvents = col.events


    segmentsDic = {}
    segmentsInfo = {}
    bytesReceivedTimes = {}
    bytesReceivedSecTimes = {}
    numBytes = 0
    curBytes = 0
    firstTimeData = -1
    # get events timestamp per segment (chunks)
    for event in colEvents:
        if event.name.startswith('chunksLog:') :
            if event.name == 'chunksLog:interest_discovery' :
                discoveryInterest = event.timestamp
            elif event.name == 'chunksLog:data_discovery' :
                discoverySegment = event['segment_number']
                discoveryData  =  event.timestamp
            elif event.name == 'chunksLog:interest_timeout' :
                if event['segment_number'] not in segmentsDic or 'chunksLog:interest_timeout' not in segmentsDic[event['segment_number']] :
                    segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, 1)
                else :
                    segmentsDic[event['segment_number']]['chunksLog:interest_timeout'] += 1
            elif event.name == 'chunksLog:interest_sent' or event.name == 'chunksLog:data_received' or event.name == 'chunksLog:interest_nack':
                segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, event.timestamp)
                for field in event.items() :
                    if field[0] == 'received_bytes' :
                        if firstTimeData == -1 :
                            firstTimeData = event.timestamp / 1e9
                        
                        if int((event.timestamp / 1e9 ) -  firstTimeData) not in bytesReceivedSecTimes :
                            curBytes = field[1]/1000
                            bytesReceivedSecTimes.setdefault(int((event.timestamp / 1e9 ) -  firstTimeData), curBytes)
                        else :
                            curBytes += field[1]/1000 ##TODO use float
                            bytesReceivedSecTimes[int((event.timestamp / 1e9 ) -  firstTimeData)] = curBytes 
                            
                        
                        numBytes += int(field[1]/1000)
                        bytesReceivedTimes.setdefault(int((event.timestamp / 1e9 ) -  firstTimeData), numBytes) #TODO
                    segmentsInfo.setdefault(event['segment_number'],{}).setdefault(event.name, {}).setdefault(field[0], field[1])
    
    # Insert segment used in discovery phase 
    segmentsDic.setdefault(discoverySegment,{}).setdefault('chunksLog:data_received', discoveryData)
    segmentsDic.setdefault(discoverySegment,{}).setdefault('chunksLog:interest_sent', discoveryInterest)
    
    startTimestamp = segmentsDic[0]['chunksLog:interest_sent']
    stopTimestamp = segmentsDic[0]['chunksLog:data_received']
    
    totSegments = 0;
    
    retriveTimes = [] # time to retrieve for each segments (from the interest sent to data received)
    timeoutRetries = [] # number of timeout for each segments
    bytesReceived = []
    for segmentNo, segmentInfo in segmentsDic.items() :
        
        # Populatate received segmetns time list
        if 'chunksLog:data_received' in segmentInfo and 'chunksLog:interest_sent' in segmentInfo :
            tot = segmentInfo['chunksLog:data_received'] - segmentInfo['chunksLog:interest_sent']
            retriveTimes.append(tot)
            
            startTimestamp = min(segmentInfo['chunksLog:interest_sent'], startTimestamp)
            stopTimestamp = max(segmentInfo['chunksLog:data_received'], stopTimestamp)
        else :
            print ("Segment not received: " + str(segmentNo))
        
        # Populate timeout list    
        if 'chunksLog:interest_timeout' in segmentInfo :
            timeoutRetries.append(segmentInfo['chunksLog:interest_timeout'])
        else :
            timeoutRetries.append(0)
            
        # Populate byte received
        
        if 'chunksLog:data_received' in segmentInfo :
            bytesReceived.append(segmentsInfo[segmentNo]['chunksLog:data_received']['received_bytes'])
        else :
            bytesReceived.append(0)
            
    ########## Print statistics
    mathTimes = np.array(retriveTimes)   # TODO use directly retrieveTimes
    mathTimeout = np.array(timeoutRetries)   # TODO use directly timeoutReties
    mathBytes = np.array(bytesReceived)   # TODO use directly timeoutReties
    
    totTime = (stopTimestamp - startTimestamp)/ 1000000000
    
    print('\n----------- Overall -----------')
    print('Total time (s)          : {:.1f}'.format(totTime))
    print('Number of segments      : {:d}'.format(len(segmentsDic)))
    print('Total received data (MB): {:.3f}'.format(mathBytes.sum()/1000000))
    print('Speed (KB/s)            : {:.3f}'.format((mathBytes.sum()/1000)/totTime))
    print('\n--------- Retrieve times ---------')
    print('Min (ms)             : {:.1f}'.format(mathTimes.min() / 1000000))
    print('Max (ms)             : {:.1f}'.format(mathTimes.max() / 1000000))
    print('Mean (ms)            : {:.1f}'.format(mathTimes.mean() / 1000000))
    print('Dev. std. (ms)       : {:.1f}'.format(mathTimes.std() / 1000000))
    print('\n---------- Timeouts ----------')
    print('Min                  : {:.1f}'.format(mathTimeout.min()))
    print('Max                  : {:.1f}'.format(mathTimeout.max()))
    print('Mean                 : {:.1f}'.format(mathTimeout.mean()))
    print('Dev. std.            : {:.1f}'.format(mathTimeout.std()))
    
    stat = []
    stat.append(('\n----------- Overall -----------', -1))
    stat.append(('Total time((s))))         : ', totTime))
    stat.append(('Number of segments      : ', len(segmentsDic)))
    stat.append(('Total received data((MB)): ', mathBytes.sum()/1000000))
    stat.append(('Speed((KB/s))))           : ', (mathBytes.sum()/1000)/totTime))
    stat.append(('\n--------- Retrieve times ---------', -1))
    stat.append(('Min((ms))))            : ', mathTimes.min()/ 1000000))
    stat.append(('Max((ms))))            : ', mathTimes.max()/ 1000000))
    stat.append(('Mean((ms))))           : ', mathTimes.mean()/ 1000000))
    stat.append(('Dev. std.((ms))))      : ', mathTimes.std()/ 1000000))
    stat.append(('\n---------- Timeouts ----------', -1))
    stat.append(('Min                  : ', mathTimeout.min()))
    stat.append(('Max                  : ', mathTimeout.max()))
    stat.append(('Mean                 : ', mathTimeout.mean()))
    stat.append(('Dev. std.            : ', mathTimeout.std()))
    
    trace1 = go.Scatter(
        x=list(range(0, len(retriveTimes) - 1)),
        y=mathTimes / 1000000
    )
    
    mean = go.Scatter(
        x=list(range(0, len(retriveTimes) - 1)),
        y= [str(mathTimes.mean() / 1000000) for i in range (0, len(retriveTimes) - 1)],
        name = 'Mean'
    )
    
    layout = {
        'autosize' : 'false',
        'yaxis' : dict(range=[0, (mathTimes.mean() / 1000000) * 2]),
        'width' : '700',
        'height' : '500',
        'title' : 'Retrieve time',
        'shapes': []
    }
    
    wlanSeg = wlanStateBySegmentNo(col, startTimestamp, stopTimestamp) 
    for seg in wlanSeg :
        layout['shapes'].append(
            {
                'type': 'rect',
                'x0': seg[0],
                'y0': 0,
                'x1': seg[1],
                'y1': mathTimes.max() / 1000000,
                'line': {
                    'color': 'rgba(128, 0, 128, 0)',
                    'width': 2,
                },
                'fillcolor': 'rgba(93, 191, 63, 0.3)',
            })
        
        
    htmlStat = "<div style = 'float: left'><table>"
    for value in stat :
        if value[1] == -1 : #TODO very bad 
            htmlStat += "<tr><td colspan='2'>" + value[0] + "</td></tr>"
        else:
            htmlStat += "<tr><td>" + value[0] + "</td><td>" + str(value[1]) + "</td></tr>"
    htmlStat += "</table></div>"
    
    resultsFile = open('results.html','w')
    
    resultsFile.write(htmlStat)
    
    data = [trace1, mean]
    fig = go.Figure(data=data, layout=layout)
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(plot(fig , output_type='div', include_plotlyjs='true'))
    resultsFile.write("</div>")
    
    ################
    mathBytesT = np.array(list(bytesReceivedTimes.keys()))
    mathBytesTSpeed = np.array(list(bytesReceivedTimes.values()))
    
    bytesTime = go.Scatter(
        x =  mathBytesT,
        y =  mathBytesTSpeed ,
        name = 'B transf'
    )
    
    layoutT = {
        'width' : '700',
        'height' : '500',
        'title' : 'Retrieve time',
        'shapes': []
    }
    
    wlanSegT = wlanStateByTimestamp(col, startTimestamp, stopTimestamp) 
    for seg in wlanSegT :
        if (seg[0] / 1e9) < firstTimeData :
            startX = 0
        else :
            startX = (seg[0] / 1e9) - firstTimeData
            
        if (seg[1] / 1e9) < firstTimeData :
            endX = 0
        else :
            endX = (seg[1] / 1e9) - firstTimeData
            
        if endX != 0 :
            layoutT['shapes'].append(
                {
                    'type': 'rect',
                    'x0': startX,
                    'y0': 0,
                    'x1': endX,
                    'y1': mathBytesTSpeed.max(),
                    'line': {
                        'color': 'rgba(128, 0, 128, 0)',
                        'width': 2,
                    },
                    'fillcolor': 'rgba(93, 191, 63, 0.3)',
                })
    
    dataTime = [bytesTime]
    figT = go.Figure(data=dataTime, layout=layoutT)
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(plot(figT , include_plotlyjs='false', output_type='div'))
    resultsFile.write("</div>")
    
    
    mathBytesTSec = np.array(list(bytesReceivedTimes.keys()))
    mathBytesTSecSpeed = np.array(list(bytesReceivedSecTimes.values()))
    
    layoutT2 = {
        'width' : '700',
        'height' : '500',
        'title' : 'Retrieve time',
        'shapes': []
    }
    
    for seg in wlanSegT :
        if (seg[0] / 1e9) < firstTimeData :
            startX = 0
        else :
            startX = (seg[0] / 1e9) - firstTimeData
            
        if (seg[1] / 1e9) < firstTimeData :
            endX = 0
        else :
            endX = (seg[1] / 1e9) - firstTimeData
            
        if endX != 0 :
            layoutT2['shapes'].append(
                {
                    'type': 'rect',
                    'x0': startX,
                    'y0': 0,
                    'x1': endX,
                    'y1': mathBytesTSecSpeed.max(),
                    'line': {
                        'color': 'rgba(128, 0, 128, 0)',
                        'width': 2,
                    },
                    'fillcolor': 'rgba(93, 191, 63, 0.3)',
                })
    
    bytesTimeSec = go.Scatter(
        x =  mathBytesTSec,
        y =  mathBytesTSecSpeed ,
        name = 'KBs Speed'
    )
    
    dataTimeSec = [bytesTimeSec]
    figT2 = go.Figure(data=dataTimeSec, layout=layoutT2)
    #plot(figT2 , filename= name + 'TimesSec.html')
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(plot(figT2 , include_plotlyjs='false', output_type='div'))
    resultsFile.write("</div>")
    
    
    resultsFile.close()
    
    print("Results written to: " + resultsFile.name)
    
def wlanStateByTimestamp(col, startTimestamp, stopTimestamp) :
    wlanStatus = []
    lastState = [startTimestamp, -1]
    for event in col.events_timestamps(startTimestamp, stopTimestamp) :
        if not event.name.startswith('chunksLog:') :
            if event.name == 'mgmtLog:network_state' and  event['interface_name'] == 'wlan0' :
                if event['interface_state'] == 'running' :
                    if (lastState[0] ==  -1) :
                        lastState[0] = event.timestamp
                else :
                    if (lastState[0] !=  -1 and lastState[1] ==  -1) :
                        lastState[1] = event.timestamp
                        wlanStatus.append(lastState)
                        lastState = [-1, -1]
                    
    if (lastState[0] !=  -1 and lastState[1] ==  -1) :
        lastState[1] = event.timestamp
        wlanStatus.append(lastState)
    
    return wlanStatus

def wlanStateBySegmentNo(col, startTimestamp, stopTimestamp) :
    wlanStatus = wlanStateByTimestamp(col, startTimestamp, stopTimestamp)
    
    wlanSeg = []
    lastSeg = [-1, -1]    
    for times in wlanStatus :
        for event in col.events_timestamps(times[0], times[1]) :
            if event.name.startswith('chunksLog:') :
                if 'segment_number' in  event :
                    if lastSeg[0] == -1 :
                        lastSeg[0] = event['segment_number']
                        lastSeg[1] = event['segment_number']
                    else :
                        lastSeg[1] = event['segment_number']
        
        if lastSeg[0] != -1 :
            wlanSeg.append(lastSeg)
            lastSeg = [-1, -1]
                    
    return wlanSeg
    
if __name__ == '__main__':
    if len(sys.argv) != 2:
        msg = 'Usage: python {} TRACEPATH'.format(sys.argv[0])
        raise ValueError(msg)
    
    chunksStatistics(sys.argv[1], -1, -1)
