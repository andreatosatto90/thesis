import sys
import babeltrace.reader
import numpy as np
import graphs
from pyndn import Name
import datetime

import os

wirelessInterfaces = [ 'wlp4s0', 'eth0']
packetSize = 1407
contentPacketSize = 1304
prodStartSlack = 2000000000# 2 sec
prodStopSlack = 2000000000

def loadCatTraces(filepath):
    # a trace collection holds one to many traces
    col = babeltrace.TraceCollection()
    
    for subDir in os.listdir(filepath):
        if not subDir.startswith("prod") :
            if col.add_trace(filepath + subDir + '/64-bit/', 'ctf') is None:
                raise RuntimeError('Cannot add cat trace')
        
    return col

def loadPutTraces(filepath):
    # a trace collection holds one to many traces
    col = babeltrace.TraceCollection()
    
    for subDir in os.listdir(filepath):
        if subDir.startswith("prod") :
            if col.add_trace(filepath + subDir + '/64-bit/', 'ctf') is None:
                raise RuntimeError('Cannot add put trace')
        
    return col

def startEventLogToList(event, exitCode = -1):
    dic = {}
    dic['timestamp'] = event.timestamp
    dic['startTime'] = event.datetime
    if 'start_pipeline_size' in event:
        dic['startPipelineSize'] = event['start_pipeline_size']
    else :
        dic['startPipelineSize'] = -1
    if 'ssthresh' in event:
        dic['ssthresh'] = event['ssthresh']
    else :
        dic['ssthresh'] = -1 
    dic['maxPipelineSize'] = event['max_pipeline_size']
    dic['interestLifetime'] = event['interest_lifetime']
    dic['maxRetries'] = event['max_retries']
    dic['mustBeFresh'] = event['must_be_fresh']
    if 'timeout_reset' in event:
        dic['timeout_reset'] = event['timeout_reset']
    else :
        dic['timeout_reset'] = -1
    if 'window_cut_multiplier' in event:
        dic['window_cut_multiplier'] = event['window_cut_multiplier']
    else :
        dic['window_cut_multiplier'] = -1
    if 'rto_reset' in event:
        dic['rto_reset'] = event['rto_reset']
    else :
        dic['rto_reset'] = -1
    dic['exitCode'] = exitCode
    return dic

def startEventPutToList(event, exitCode = -1):
    dic = {}
    dic['timestamp'] = event.timestamp
    dic['startTime'] = event.datetime
    dic['prefix'] = event['prefix']
    dic['signingInfo'] = event['signing_info']
    dic['freshness'] = event['freshness']
    dic['maxSegmentSize'] = event['max_segment_size']
    dic['numberOfSegments'] = event['number_of_segments']
    return dic

def getSessions(filepath):
    col = loadCatTraces(filepath)
    sessions = []

    lastStartEvent = None
    lastEventTimestamp = col.timestamp_begin
    # get events per segment (chunks)
    for event in col.events_timestamps(col.timestamp_begin, col.timestamp_end) :
        if event.name == 'chunksLog:cat_started' :
            if lastStartEvent != None :
                sessions.append([lastStartEvent, lastEventTimestamp])
                lastStartEvent = startEventLogToList(event)
            else :
                lastStartEvent = startEventLogToList(event)
        elif event.name == 'chunksLog:cat_stopped' :
           if lastStartEvent != None :
                lastStartEvent['exitCode'] = event['exit_code']
                sessions.append([lastStartEvent, event.timestamp])
                lastStartEvent = None   
        lastEventTimestamp = event.timestamp
    
    if lastStartEvent != None :
        sessions.append([lastStartEvent, col.timestamp_end])
    
    return sessions

def getPutInput(col, startTimestamp):
    lastStartEvent = None
    
    if startTimestamp < col.timestamp_begin :
        for event in col.events_timestamps(col.timestamp_begin, col.timestamp_end) :
            if event.name == 'chunksLog:put_started' :
                lastStartEvent = startEventPutToList(event)
                break
    else:
        for event in col.events_timestamps(col.timestamp_begin, startTimestamp + prodStopSlack) :
            if event.name == 'chunksLog:put_started' :
                lastStartEvent = startEventPutToList(event)
    
    return lastStartEvent

def chunksStatistics(filepath, start, stop, session, noProd):
    col = loadCatTraces(filepath)
    
    if start != -1 and stop != -1 :
        colEvents = col.events_timestamps(start, stop)
    else :
        colEvents = col.events

    segmentsDic = {}
    segmentsInfo = {}
    bytesReceivedTimes = {}
    bytesReceivedSecTimes = {}
    packetSentSecTimes = {}
    curSent = 0;
    packetReceivedSecTimes = {}
    curReceived = 0;
    packetReceivedErrorSecTimes = {}
    curReceivedError = 0;
    packetSentErrorSecTimes = {}
    curSentError = 0;
    windowSizeTime = {}
    windowMultiplier = {}
    windowRttReset = {}
    curWindowSize = 0;
    numBytes = 0
    curBytes = 0
    firstTimeData = -1 #seconds
    firstTimeDataMs = -1
    lastTimeData = -1
    
    discoverySegment = 0
    discoveryInterest = start
    discoveryData  =  start
    # get events timestamp per segment (chunks)
    usedStrategies = []
    rtts = {}
    rttsMean = {}
    numRtt = 0
    
    rttTime = {}
    
    rttTimeMean = {}
    
    rttMin = {}
    rttMax = {}
    rttMinCalc ={}
    
    dataRejected = {}
    
    rttChunks = {}
    
    minRttMinCalc = 1000000;
    
    countPacket = 0
    countSegment = 0
    
    lifetimeTime = {}
    
    for event in colEvents:
        if event.name.startswith('chunksLog:') :
            if event.name == 'chunksLog:interest_discovery' :
                discoveryInterest = event.timestamp
            elif event.name == 'chunksLog:data_discovery' :
                discoverySegment = event['segment_number']
                discoveryData  =  event.timestamp
            elif event.name == 'chunksLog:interest_timeout' or event.name == 'chunksLog:data_sent' : #remove data sent
                if event['segment_number'] not in segmentsDic or event.name not in segmentsDic[event['segment_number']] :
                    segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, 1)
                else :
                    segmentsDic[event['segment_number']][event.name] += 1
            elif event.name == 'chunksLog:interest_sent' or event.name == 'chunksLog:data_received' or event.name == 'chunksLog:interest_nack':
                segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, event.timestamp)
                
                if event.name == 'chunksLog:interest_sent' :
                    if 'lifetime' in event :
                        if firstTimeData == -1 :
                            firstTimeData = event.timestamp / 1e9
                            firstTimeDataMs = event.timestamp / 1e6
                        
                        slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                        #print(slot)
                        if slot not in lifetimeTime :
                            lifetimeTime.setdefault(slot, (event['lifetime'], 1))
                        else :
                            (r, c) = lifetimeTime[slot]
                            lifetimeTime[slot] = (r + event['lifetime'], c+1)
                
                if event.name == 'chunksLog:data_received' :
                    countSegment += 1
                    if 'rtt' in event :
                        #rtts.setdefault(numRtt, event['rtt'])
                        if firstTimeData == -1 :
                            firstTimeData = event.timestamp / 1e9
                            firstTimeDataMs = event.timestamp / 1e6
                        
                        slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                        #print(slot)
                        if  slot not in rttChunks :
                            rttChunks.setdefault(slot, (event['rtt'], 1))
                        else :
                            (r, c) = rttChunks[slot]
                            rttChunks[slot] = (r + event['rtt'], c+1)
                    
                for field in event.items() :
                    if field[0] == 'bytes' :
                        if firstTimeData == -1 :
                            firstTimeData = event.timestamp / 1e9
                            firstTimeDataMs = event.timestamp / 1e6
                        
                        slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                        if slot not in bytesReceivedSecTimes :
                            curBytes = packetSize/100 #float(field[1])/100
                            bytesReceivedSecTimes.setdefault(slot, curBytes)
                        else :
                            curBytes += packetSize/100 #float(field[1])/100
                            bytesReceivedSecTimes[slot] = curBytes
                        
                        numBytes += packetSize/100 #float(field[1])/100
                        bytesReceivedTimes.setdefault(slot, numBytes) #TODO
                        
                        if lastTimeData < slot :
                            lastTimeData = slot
                    segmentsInfo.setdefault(event['segment_number'],{}).setdefault(event.name, {}).setdefault(field[0], field[1])
                    
            elif event.name =='chunksLog:window' :
                if firstTimeData == -1 :
                    firstTimeData = event.timestamp / 1e9
                    firstTimeDataMs = event.timestamp / 1e6
                    
                slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                if  slot not in windowSizeTime :
                    windowSizeTime.setdefault(slot, (event['size'], 1))
                else :
                    (r, c) = windowSizeTime[slot]
                    windowSizeTime[slot] = (r + event['size'], c+1)
                    
            elif event.name =='chunksLog:rtoMulti_change' :
                if firstTimeData == -1 :
                    firstTimeData = event.timestamp / 1e9
                    firstTimeDataMs = event.timestamp / 1e6
                    
                slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                if  slot not in windowMultiplier :
                    windowMultiplier.setdefault(slot, (event['size'], 1))
                else :
                    (r, c) = windowMultiplier[slot]
                    windowMultiplier[slot] = (int(event['size']), 1)
                    
            elif event.name =='chunksLog:rtt_reset' :
                if firstTimeData == -1 :
                    firstTimeData = event.timestamp / 1e9
                    firstTimeDataMs = event.timestamp / 1e6
                    
                slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                if  slot not in windowRttReset :
                    windowRttReset.setdefault(slot, (1, 1))
                else :
                    (r, c) = windowRttReset[slot]
                    windowRttReset[slot] = (r + 1, 1)
                    
                    
        elif event.name.startswith('strategyLog:') :
            if event.name == 'strategyLog:interest_sent' or event.name == 'strategyLog:data_received':
                    
                if event.name == 'strategyLog:data_received' :
                    if event['strategy_name'] not in usedStrategies :
                        usedStrategies.append(event['strategy_name'])
                    
                    if 'rtt' in event :
                        if event['rtt'] != -1 :
                            #rtts.setdefault(numRtt, event['rtt'])
                            if firstTimeData == -1 :
                                firstTimeData = event.timestamp / 1e9
                                firstTimeDataMs = event.timestamp / 1e6
                            
                            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                            #print(slot)
                            if  slot not in rttTime :
                                rttTime.setdefault(slot, (event['rtt'], 1))
                            else :
                                (r, c) = rttTime[slot]
                                rttTime[slot] = (r + event['rtt'], c+1)
                        
                    if 'mean_rtt' in event :
                        if event['mean_rtt'] != -1 :
                            #rttsMean.setdefault(numRtt, event['mean_rtt'])
                            if firstTimeData == -1 :
                                firstTimeData = event.timestamp / 1e9
                                firstTimeDataMs = event.timestamp / 1e6
                            
                            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
                            #print(slot)
                            if  slot not in rttTimeMean :
                                rttTimeMean.setdefault(slot, (event['mean_rtt'], 1))
                            else :
                                (r, c) = rttTimeMean[slot]
                                rttTimeMean[slot] = (r + event['mean_rtt'], c+1)
                    numRtt += 1
                    
                    if 'num_retries' in event :
                        segmentComponent = event['interest_name'].split("?")[0]
                        lol = Name(segmentComponent)
                        if lol.get(-1).isSegment() :
                            segmentsDic.setdefault(lol.get(-1).toSegment(), {}).setdefault('num_retries', event['num_retries'])
                    
        if event.name == 'faceLog:packet_sent' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetSentSecTimes :
                curSent = 1
                packetSentSecTimes.setdefault(slot, curSent)
            else :
                curSent += 1
                packetSentSecTimes[slot] = curSent
                
        elif event.name == 'faceLog:packet_received' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
                
            countPacket += 1
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetReceivedSecTimes :
                curReceived = 1
                packetReceivedSecTimes.setdefault(slot, curReceived)
            else :
                curReceived += 1
                packetReceivedSecTimes[slot] = curReceived
                
        elif event.name == 'faceLog:packet_received_error' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetReceivedErrorSecTimes :
                curReceivedError = 1
                packetReceivedErrorSecTimes.setdefault(slot, curReceivedError)
            else :
                curReceivedError += 1
                packetReceivedErrorSecTimes[slot] = curReceivedError
                
        elif event.name == 'faceLog:packet_sent_error' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetSentErrorSecTimes :
                curSentError = 1
                packetSentErrorSecTimes.setdefault(slot, curSentError)
            else :
                curSentError += 1
                packetSentErrorSecTimes[slot] = curSentError
                
        
        elif event.name == 'strategyLog:rtt_min' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if  slot not in rttMin :
                rttMin.setdefault(slot, (event['rtt_min'], 1))
            else :
                (r, c) = rttMin[slot]
                rttMin[slot] = (r + event['rtt_min'], c+1)
            
        elif event.name == 'strategyLog:rtt_max' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
                
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if  slot not in rttMax :
                rttMax.setdefault(slot, (event['rtt_max'], 1))
            else :
                (r, c) = rttMax[slot]
                rttMax[slot] = (r + event['rtt_max'], c+1)
                
        elif event.name == 'strategyLog:rtt_min_calc' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
             
             
            if event['rtt_min_calc'] < minRttMinCalc :
                minRttMinCalc = event['rtt_min_calc']
                
                
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if  slot not in rttMinCalc :
                rttMinCalc.setdefault(slot, (event['rtt_min_calc'], 1))
            else :
                (r, c) = rttMinCalc[slot]
                rttMinCalc[slot] = (r + event['rtt_min_calc'], c+1)
                
        elif event.name == 'strategyLog:data_rejected' :
            if firstTimeData == -1 :
                firstTimeData = event.timestamp / 1e9
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in dataRejected :
                dataRejected.setdefault(slot, 1)
            else :
                dataRejected[slot] = dataRejected[slot] + 1
        #elif event.name.startswith('strategyLog:') :
                    
    
    print("End first part, Packets " + str(countPacket) + " segments " + str(countSegment))
    if not noProd :
        for event in loadPutTraces(filepath).events_timestamps(start - prodStartSlack, stop + prodStopSlack):
            if event.name == 'chunksLog:data_sent' :
                if event['segment_number'] not in segmentsDic or event.name not in segmentsDic[event['segment_number']] :
                    segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, 1)
                else :
                    segmentsDic[event['segment_number']][event.name] += 1

    
       
    # insert 0 where values is missing
    for i in range (0, lastTimeData) :
        if i not in bytesReceivedSecTimes :
            bytesReceivedSecTimes.setdefault(i,0)
            
    # insert last value where values is missing
    lastValue = 0
    for i in range (0, lastTimeData) :
        if i not in bytesReceivedTimes :
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
    stratRetries = [] # number of strategy retries for each segment
    bytesReceived = []
    datasSent = [] # number of data sent for each segments
    for segmentNo, segmentInfo in segmentsDic.items() :
        
        # Populatate received segments time list
        if 'chunksLog:data_received' in segmentInfo and 'chunksLog:interest_sent' in segmentInfo :
            tot = segmentInfo['chunksLog:data_received'] - segmentInfo['chunksLog:interest_sent']
            retriveTimes.append(tot)
            
            startTimestamp = min(segmentInfo['chunksLog:interest_sent'], startTimestamp)
            stopTimestamp = max(segmentInfo['chunksLog:data_received'], stopTimestamp)
        #else :
            #print ("Segment not received: " + str(segmentNo))
        
        # Populate timeout list    
        if 'chunksLog:interest_timeout' in segmentInfo :
            timeoutRetries.append(segmentInfo['chunksLog:interest_timeout'])
        else :
            timeoutRetries.append(0)
            
        # Populate data sent list    
        if 'chunksLog:data_sent' in segmentInfo :
            datasSent.append(segmentInfo['chunksLog:data_sent'])
        else :
            datasSent.append(0)
            
        if 'num_retries' in segmentInfo :
            stratRetries.append(segmentInfo['num_retries'])
        else :
            stratRetries.append(0)
            
        # Populate byte received
        
        if 'chunksLog:data_received' in segmentInfo :
            if segmentNo in segmentsInfo:
                if 'chunksLog:data_received' in segmentsInfo[segmentNo] :
                    bytesReceived.append(packetSize) #segmentsInfo[segmentNo]['chunksLog:data_received']['bytes']
                else :
                    bytesReceived.append(0)
            else :
                bytesReceived.append(0)   
        else :
            bytesReceived.append(0)
            
    ########## Print statistics
    mathTimes = np.array(retriveTimes)   # TODO use directly retrieveTimes
    mathTimeout = np.array(timeoutRetries)   # TODO use directly timeoutReties
    mathBytes = np.array(bytesReceived)   # TODO use directly timeoutReties
    mathDatasSent = np.array(datasSent)
    mathStratRetries = np.array(stratRetries)
    
    totTime = (stopTimestamp - startTimestamp)/ 1000000000
    
    # print('\n----------- Overall -----------')
    # print('Total time (s)          : {:.1f}'.format(totTime))
    # print('Number of segments      : {:d}'.format(len(segmentsDic)))
    # print('Total received data (MB): {:.3f}'.format(mathBytes.sum()/1000000))
    # print('Speed (KB/s)            : {:.3f}'.format((mathBytes.sum()/1000)/totTime))
    # print('\n--------- Retrieve times ---------')
    # print('Min (ms)             : {:.1f}'.format(mathTimes.min() / 1000000))
    # print('Max (ms)             : {:.1f}'.format(mathTimes.max() / 1000000))
    # print('Mean (ms)            : {:.1f}'.format(mathTimes.mean() / 1000000))
    # print('Dev. std. (ms)       : {:.1f}'.format(mathTimes.std() / 1000000))
    # print('\n---------- Timeouts ----------')
    # print('Min                  : {:.1f}'.format(mathTimeout.min()))
    # print('Max                  : {:.1f}'.format(mathTimeout.max()))
    # print('Mean                 : {:.1f}'.format(mathTimeout.mean()))
    # print('Dev. std.            : {:.1f}'.format(mathTimeout.std()))
    
    wlanSeg = wlanStateBySegmentNo(col, startTimestamp, stopTimestamp)
    wlanSegT = wlanStateByTimestamp(col, startTimestamp, stopTimestamp)
    
    history = getSessionHistory(col, start, stop)
    
    putStart = None
    putPacketSent = {}
    putPacketRec = {}
    
    if not noProd :
        colPut = loadPutTraces(filepath)
        putStart = getPutInput(colPut, start)
        if putStart != None :
            (putPacketSent, putPacketRec) = getPutPackets(colPut, start , stop)
        
    
    i = 0
    while i < max(len(packetReceivedSecTimes), len(packetSentSecTimes)) :
        if i not in packetSentSecTimes.keys() :
            packetSentSecTimes.setdefault(i, 0);
        if i not in packetReceivedSecTimes.keys() :
            packetReceivedSecTimes.setdefault(i, 0);
        i += 1
        
    i = 0
    # while i < max(len(rttTime), len(rttTimeMean)) :
    #     if i not in rttTime.keys() :
    #         rttTime.setdefault(i, (0,1));
    #     if i not in rttTimeMean.keys() :
    #         rttTimeMean.setdefault(i, (0,1));
    #     i += 1
    
    #getInterestRetries(col, wlanSegT)
    
    if totTime > 0 :
        graphs.statToHtml(session, putStart, stopTimestamp, totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, mathStratRetries, \
                          mathDatasSent, bytesReceivedTimes, wlanSeg, wlanSegT, firstTimeData, bytesReceivedSecTimes, \
                          usedStrategies, history, packetSentSecTimes, packetReceivedSecTimes, putPacketSent, putPacketRec, packetReceivedErrorSecTimes, \
                          packetSentErrorSecTimes, rtts, rttsMean, rttTime, rttTimeMean, rttMin, rttMax, rttMinCalc, rttChunks, firstTimeDataMs, packetSize, \
                          windowSizeTime, windowMultiplier, dataRejected, lifetimeTime, windowRttReset)
    else :
        print("Not enough data, skipping results generation for this session")
  
class addressStat(object):
    def __init__(self, address) :
        self.address = address
        self.bytesIn = 0
        self.packetsIn = 0
        self.bytesOut = 0
        self.packetsOut = 0
        
    def incrementValues(self, event) :
        if event.name == 'faceLog:packet_sent' :
            self.bytesOut += float(event['bytes'])
            self.packetsOut += 1
        elif event.name == 'faceLog:packet_received' :
            self.bytesIn += float(event['bytes'])
            self.packetsIn += 1
            
    def getHtmlTable(self, durationMs) :
        htmlStat = "<table class='address'>"
        htmlStat += "<tr><th colspan='3'> Address: " + self.address + "</th></tr>"
        
        htmlStat += "<tr><td>In pkts</td><td>In Bytes</td><td>In Speed</td></tr>"
        htmlStat += "<tr><td>" + str(self.packetsIn) + "</td><td>" + str(self.bytesIn / 1000) + " KB</td><td>{0:.2f} KB/s</td></tr>".format((self.bytesIn / 1000)  / (durationMs / 1e3))
        
        htmlStat += "<tr><td>Out pkts</td><td>Out Bytes</td><td>Out Speed</td></tr>"
        htmlStat += "<tr><td>" + str(self.packetsOut) + "</td><td>" + str(self.bytesOut / 1000) + " KB</td><td>{0:.2f} KB/s</td></tr>".format((self.bytesOut / 1000)  / (durationMs / 1e3))
           
        htmlStat += "</table>"
        
        return htmlStat

class section(object):
    #startTimestamp; #ms
    #endTimestamp; #ms
    #interfaceName;
    #status;
    
    def __init__(self, startTimestamp, interfaceName, status) :
        self.startTimestamp = startTimestamp
        self.stopTimestamp = None
        self.interfaceName = interfaceName
        self.status = status
        self.addressStat = {}
        self.data = 0
        self.interest = 0
        self.timeout = 0 # TODO set 0
        #self.timeouts = 0
        
    def __str__(self) :
        return str(self.startTimestamp) + " " + str(self.stopTimestamp) + " " + self.interfaceName + " status: " + self.status + " "
    
    def durationMs(self) :
        return (self.stopTimestamp - self.startTimestamp) / 1e6;
    
    def incrementValues(self, event) :
        if event.name == 'chunksLog:interest_timeout' :
            self.timeout += 1
        elif event.name == 'chunksLog:data_received' :
            self.data += 1
        elif event.name == 'chunksLog:interest_sent' :
            self.interest += 1
    
    def getHtmlTable(self) :
        htmlStat = "<table>"
        htmlStat += "<tr><th colspan='3'>" + self.interfaceName + " " + self.status + "</th></tr>"
        htmlStat += "<tr><td> Duration (s) : </td><td colspan='2'>" + str(self.durationMs() / 1e3) + "</td></tr>"
        
        htmlStat += "<tr><td>Data</td><td>Interest</td><td>Timeouts</td></tr>"
        htmlStat += "<tr><td>" + str(self.data) + " </td><td>" + str(self.interest) + " </td><td>" + str(self.timeout) + " </td></tr>"
        
        for key, value in self.addressStat.items() :
            htmlStat += "<tr style='background-color: #FFFFFF'><td></td><td colspan ='2'>"
            htmlStat += value.getHtmlTable(self.durationMs())
            htmlStat += "</td></tr>"
            
        htmlStat += "</table>"
    
        return htmlStat
    
def aggregateState(newState, oldState) :
    if newState == oldState :
        return True;
    elif newState == 'running' : #oldState is not running state
        return False;
    elif oldState != 'running' : #newState is not running state
        return True;
    else:
        return False;
        
def getSessionHistory(col, start, stop) :
    
    lastName = "wlp4s0"
    lastState = "running"
    lastTime = 0
    stateChange = [] 
    
    if start != -1 and stop != -1 :
        colEvents = col.events_timestamps(start, stop)
        for event in col.events_timestamps(col.timestamp_begin, start) :
            if event.name == 'mgmtLog:network_state':
                lastName = event['interface_name']
                lastState = event['interface_state']
                lastTime = start
        
        if lastTime != 0 :
            stateChange.append(section(lastTime, lastName, lastState))
        else :
            lastTime = start
            stateChange.append(section(lastTime, lastName, lastState))
    else :
        colEvents = col.events
    
       
    # Search for network state changes
    #if lastState == "" :
        #lastState = 'running'
    for event in colEvents :
        if event.name == 'mgmtLog:network_state':
            stateChange.append(section(event.timestamp, event['interface_name'], event['interface_state']))
    
    
    
    previousSec = None
    filteredStateChange = []
    for sec in stateChange :
        # remove duplicate event and group not running state
        if previousSec == None :
            filteredStateChange.append(sec)
            previousSec = sec
        if not aggregateState(sec.status, previousSec.status) :
            filteredStateChange.append(sec)
            previousSec.stopTimestamp = sec.startTimestamp - 1
            previousSec = sec
            
        previousSec.stopTimestamp = stop
    
    # TODO search network change event before startTimestamp
    # if len(filteredStateChange) == 0 :
    #     sec = section(start, "Uknown", "Uknown")
    #     sec.stopTimestamp = stop
    # else :
    #     if lastState == "":
    #         lastName = "Uknown"
    #         lastState =  "Uknown"
    #     sec = section(start, lastName, lastState)
    #     sec.stopTimestamp = filteredStateChange[0].stopTimestamp
    #     filteredStateChange = [sec] + filteredStateChange
        
    for sec in filteredStateChange:
        for event in col.events_timestamps(sec.startTimestamp, sec.stopTimestamp) :
            if 'local_endpoint' in event :
                addrStat = sec.addressStat.setdefault(event['local_endpoint'], addressStat(event['local_endpoint']))
                addrStat.incrementValues(event)
            else :
                sec.incrementValues(event)
    
    return filteredStateChange
    
    
    
def wlanStateByTimestamp(col, startTimestamp, stopTimestamp) :
    history = getSessionHistory(col, startTimestamp, stopTimestamp)
    wlanStatus = []
        
    for his in history :
        if his.status == 'running' :
            wlanStatus.append([his.startTimestamp, his.stopTimestamp])
            
    return wlanStatus

def wlanStateBySegmentNo(col, startTimestamp, stopTimestamp) :
    wlanStatus = wlanStateByTimestamp(col, startTimestamp, stopTimestamp)
    
    wlanSeg = []
    lastSeg = [-1, -1]
    lastSegment = -1
    for times in wlanStatus :
        for event in col.events_timestamps(times[0], times[1]) :
            if event.name.startswith('chunksLog:') :
                if 'segment_number' in event and event['segment_number'] > lastSegment:
                    if 'segment_number' in  event :
                        if lastSeg[0] == -1 :
                            lastSeg[0] = event['segment_number']
                            lastSeg[1] = event['segment_number']
                        else :
                            lastSeg[1] = event['segment_number']
                        
                        lastSegment = lastSeg[1]
        
        if lastSeg[0] != -1 :
            wlanSeg.append(lastSeg)
            lastSeg = [-1, -1]
                    
    return wlanSeg

def getPutPackets(col, start, stop) :
    
    firstTimeDataMs = -1
    packetSentSecTimes = {}
    curSent = 0;
    packetReceivedSecTimes = {}
    curReceived = 0;

    start = start - prodStartSlack # 2 sec
    stop = stop + prodStopSlack
    
    for event in col.events_timestamps(start, stop):
        if event.name == 'faceLog:packet_sent' :
            if firstTimeDataMs == -1 :
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetSentSecTimes :
                curSent = 0
                packetSentSecTimes.setdefault(slot, curSent)
            else :
                curSent += 1
                packetSentSecTimes[slot] = curSent
                
        elif event.name == 'faceLog:packet_received' :
            if firstTimeDataMs == -1 :
                firstTimeDataMs = event.timestamp / 1e6
            
            slot = int(((event.timestamp / 1e6 ) -  firstTimeDataMs) / 100)
            if slot not in packetReceivedSecTimes :
                curReceived = 0
                packetReceivedSecTimes.setdefault(slot, curReceived)
            else :
                curReceived += 1
                packetReceivedSecTimes[slot] = curReceived
    
    i = 0         
    while i < max(len(packetReceivedSecTimes), len(packetReceivedSecTimes)) :
        if i not in packetSentSecTimes.keys() :
            packetSentSecTimes.setdefault(i, 0);
        if i not in packetReceivedSecTimes.keys() :
            packetReceivedSecTimes.setdefault(i, 0);
        
        i += 1
                
    return (packetSentSecTimes, packetReceivedSecTimes)

# def getInterestRetries(col, wlanSegT) :
#     rttMean = {}
#     pendingInterest = {}
#     receivedInterest = {}
#     for seg in wlanSegT :
#         for event in col.events_timestamps(seg[0], seg[1]) :
#             if event.name == 'strategyLog:interest_sent' :
#                 segmentComponent = event['interest_name'].split("?")[0]
#                 lol = Name(segmentComponent)
#                 if lol.get(-1).isSegment() :
#                     pendingInterest.setdefault(lol.get(-1).toSegment(), []).append(event.timestamp)
#             elif event.name == 'strategyLog:data_received' :
#                 rttMean.setdefault(event.timestamp, event['mean_rtt'])
#                 segmentComponent = event['interest_name'].split("?")[0]
#                 lol = Name(segmentComponent)
#                 if lol.get(-1).isSegment() :
#                     receivedInterest.setdefault(lol.get(-1).toSegment(), event.timestamp)
#     
#     for pi in  pendingInterest :               
#         for seg in wlanSegT :
#             for event in col.events_timestamps(seg[0], seg[1]) :
#                 if pi < seg[0] :
                    
            
        