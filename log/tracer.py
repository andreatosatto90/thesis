import sys
import babeltrace.reader
import numpy as np
import graphs

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

def chunksStatistics(filepath, start, stop, session):
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
    lastTimeData = -1
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
                        
                        if lastTimeData < int((event.timestamp / 1e9 ) -  firstTimeData) :
                            lastTimeData = int((event.timestamp / 1e9 ) -  firstTimeData)
                    segmentsInfo.setdefault(event['segment_number'],{}).setdefault(event.name, {}).setdefault(field[0], field[1])
    
    # insert 0 where values is missing
    for i in range (0, lastTimeData) :
        if i not in bytesReceivedSecTimes :
            bytesReceivedSecTimes.setdefault(i,0)
            
    # insert last value where values is missing
    lastValue = 0
    for i in range (0, lastTimeData) :
        if i not in bytesReceivedTimes :
            print (str(i))
            bytesReceivedTimes.setdefault(i, lastValue)
        lastValue = bytesReceivedTimes[i]
            
            
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
    
    wlanSeg = wlanStateBySegmentNo(col, startTimestamp, stopTimestamp)
    wlanSegT = wlanStateByTimestamp(col, startTimestamp, stopTimestamp)
    
    graphs.statToHtml(session, totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, bytesReceivedTimes, wlanSeg, wlanSegT, firstTimeData, bytesReceivedSecTimes)
    
    
    
    
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
