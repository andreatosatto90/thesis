import sys
import babeltrace.reader
import numpy as np

def chunksStatistics():
    if len(sys.argv) != 2:
        msg = 'Usage: python {} TRACEPATH'.format(sys.argv[0])
        raise ValueError(msg)

    # a trace collection holds one to many traces
    col = babeltrace.TraceCollection()

    # add the trace provided by the user
    # (LTTng traces always have the 'ctf' format)
    if col.add_trace(sys.argv[1], 'ctf') is None:
        raise RuntimeError('Cannot add trace')

    segmentsDic = {}
    # get events per segment
    for event in col.events:
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
        else :
            segmentsDic.setdefault(event['segment_number'],{}).setdefault(event.name, event.timestamp)
    
    # Insert segment used in discovery phase 
    segmentsDic.setdefault(discoverySegment,{}).setdefault('chunksLog:data_received', discoveryData)
    segmentsDic.setdefault(discoverySegment,{}).setdefault('chunksLog:interest_sent', discoveryInterest)
    
    startTimestamp = segmentsDic[0]['chunksLog:interest_sent']
    stopTimestamp = segmentsDic[0]['chunksLog:data_received']
    
    totSegments = 0;
    
    retriveTimes = [] # time to retrieve for each segments (from the interest sent to data received)
    timeoutRetries = [] # number of timeout for each segments
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
            
            
    ########## Print statistics
    mathTimes = np.array(retriveTimes)   # TODO use directly retrieveTimes
    mathTimeout = np.array(timeoutRetries)   # TODO use directly timeoutReties
    print('\n----------- Overall -----------')
    print('Total time (s): ' + str((stopTimestamp - startTimestamp)/ 1000000000))
    print('Number of segments: ' + str(len(segmentsDic)))
    print('\n----------- Retrieve times -----------')
    print('Min (ms): ' + str(mathTimes.min() / 1000000))
    print('Max (ms): ' + str(mathTimes.max() / 1000000))
    print('Mean (ms): ' + str(mathTimes.mean() / 1000000))
    print('Dev. std. (ms): ' + str(mathTimes.std() / 1000000))
    print('\n----------- Timeouts -----------')
    print('Min : ' + str(mathTimeout.min()))
    print('Max : ' + str(mathTimeout.max()))
    print('Mean : ' + str(mathTimeout.mean()))
    print('Dev. std. : ' + str(mathTimeout.std()))


if __name__ == '__main__':
    chunksStatistics()
