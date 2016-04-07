import sys
import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
import datetime

import os, os.path

graphWidth = 800
graphHeight = 600

includeLibrary = True

def timestampToDate(timestamp) :
    return  datetime.datetime.fromtimestamp(timestamp / 1e9).strftime('%Y-%m-%d %H:%M:%S')

def tableInput(ses, putStart) :
    errorString = 'Yes'
    if (ses[0]['exitCode'] != 0) :
            errorString = 'No'
    
    stat = []
    stat.append(('Catchunks Input parameters ', -1))
    stat.append(('Started : ', timestampToDate(ses[0]['timestamp'])))
    stat.append(('Finished : ', timestampToDate(ses[1])))
    stat.append(('Completed: ', errorString ))
    stat.append(('Duration (s) :', (ses[1] - ses[0]['timestamp']) / 1000000000))
    stat.append(('Max Pipeline size : ', str(ses[0]['maxPipelineSize'])))
    stat.append(('Interest lifetime (ms) : ', str(ses[0]['interestLifetime'])))
    stat.append(('Max retries  : ', str(ses[0]['maxRetries'])))
    stat.append(('Must be fresh : ', str(ses[0]['mustBeFresh'])))
    
    if putStart is not None :
        stat.append(('Putchunks Input parameters ', -1))
        stat.append(('Started : ', timestampToDate(putStart['timestamp'])))
        stat.append(('Prefix: ', putStart['prefix']))
        stat.append(('SigningInfo :', putStart['signingInfo']))
        stat.append(('Freshness : ', putStart['freshness'] ))
        stat.append(('Max segment size : ', putStart['maxSegmentSize']))
        stat.append(('Number of segments  : ', putStart['numberOfSegments']))
    
    htmlStat = "<div><table>"
    for value in stat :
        if value[1] == -1 : #TODO very bad 
            htmlStat += "<tr><th colspan='2'>" + value[0] + "</th></tr>"
        else:
            htmlStat += "<tr><td>" + value[0] + "</td><td>" + str(value[1]) + "</td></tr>"
    htmlStat += "</table></div>"
    
    return htmlStat

def tableResults(totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, usedStrategies) :
    stat = []
    stat.append(('Overall', -1))
    stat.append(('Strategies : ', '<br/>'.join(usedStrategies)))
    stat.append(('Total time (s) : ', totTime))
    stat.append(('Number of segments : ', len(segmentsDic)))
    stat.append(('Total received data (MB): ', mathBytes.sum()/1000000))
    stat.append(('Speed (KB/s) : ', (mathBytes.sum()/1000)/totTime))
    stat.append(('Retrieve times (Chunks)', -1))
    stat.append(('Min (ms) : ', mathTimes.min()/ 1000000))
    stat.append(('Max (ms) : ', mathTimes.max()/ 1000000))
    stat.append(('Mean (ms) : ', mathTimes.mean()/ 1000000))
    stat.append(('Dev. std. (ms) : ', mathTimes.std()/ 1000000))
    stat.append(('Timeouts (Chunks)', -1))
    stat.append(('Min : ', mathTimeout.min()))
    stat.append(('Max : ', mathTimeout.max()))
    stat.append(('Mean : ', mathTimeout.mean()))
    stat.append(('Dev. std. : ', mathTimeout.std()))
    
    htmlStat = "<div><table>"
    for value in stat :
        if value[1] == -1 : #TODO very bad 
            htmlStat += "<tr><th colspan='2'>" + value[0] + "</th></tr>"
        else:
            htmlStat += "<tr><td>" + value[0] + "</td><td>" + str(value[1]) + "</td></tr>"
    htmlStat += "</table></div>"
    
    return htmlStat

def tableHistory(history) :
    
    htmlStat = "<div><table>"
    for sec in history :
        htmlStat += sec.getHtmlTable()
        
    htmlStat += "</table></div>"
    
    return htmlStat


def graphTimesSegments(mathTimes, wlanSeg) :
    trace1 = go.Scatter(
        x = list(range(0, len(mathTimes) - 1)),
        y = mathTimes / 1000000,
        name = 'Retrieval time'
    )
    
    mean = go.Scatter(
        x = list(range(0, len(mathTimes) - 1)),
        y = [str(mathTimes.mean() / 1000000) for i in range (0, len(mathTimes) - 1)],
        name = 'Mean'
    )
    
    layout = {
        'autosize' : 'false',
        'yaxis' : dict(title='Time (ms)'), #range=[0, (mathTimes.mean() / 1000000) * 2]
        'xaxis' : dict(title='Segment number'),
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : 'Retrieval time for each segment (Chunks)',
        'shapes': [],
        'showlegend' : True
    }
    
    # for seg in wlanSeg :
    #     layout['shapes'].append(
    #         {
    #             'type': 'rect',
    #             'x0': seg[0],
    #             'y0': 0,
    #             'x1': seg[1],
    #             'y1': mathTimes.max() / 1000000,
    #             'line': {
    #                 'color': 'rgba(128, 0, 128, 0)',
    #                 'width': 2,
    #             },
    #             'fillcolor': 'rgba(93, 191, 63, 0.3)',
    #         })
        
    data = [trace1, mean]
    fig = go.Figure(data=data, layout=layout)
    
    htmlGraph = "<div>" #style = 'float: left'
    htmlGraph += plot(fig , output_type='div', include_plotlyjs=includeLibrary)
    htmlGraph += "</div>"
    
    return htmlGraph

def graphTimeoutSegments(mathTimeout, mathDatasSent, wlanSeg) :
    trace1 = go.Bar(
        x = list(range(0, len(mathTimeout) - 1)),
        y = mathTimeout,
        name = 'Timeouts'
    )
    
    trace2 = go.Bar(
        x = list(range(0, len(mathDatasSent) - 1)),
        y = mathDatasSent,
        name = 'Data sent'
    )
    
    layout = {
        'autosize' : 'false',
        'yaxis' : dict(title='# of events'), #range=[0, mathTimeout.mean()]
        'xaxis' : dict(title='Segment number'),
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : 'Number of timeout and data for each segment (Chunks)',
        'barmode' : 'overlay',
        'shapes': [] ,
        'showlegend' : True
            
    }
    
    # for seg in wlanSeg :
    #     layout['shapes'].append(
    #         {
    #             'type': 'rect',
    #             'x0': seg[0],
    #             'y0': 0,
    #             'x1': seg[1],
    #             'y1': max(mathTimeout.max(), mathDatasSent.max()),
    #             'line': {
    #                 'color': 'rgba(128, 0, 128, 0)',
    #                 'width': 2,
    #             },
    #             'fillcolor': 'rgba(93, 191, 63, 0.3)',
    #         })
        
    data = [trace1, trace2]
    fig = go.Figure(data=data, layout=layout)
    
    htmlGraph = "<div>" #style = 'float: left'
    htmlGraph += plot(fig , output_type='div', include_plotlyjs=includeLibrary)
    htmlGraph += "</div>"
    
    return htmlGraph

def graphBytesTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData) :
    mathBytesT = np.array(list(bytesReceivedTimes.keys()))
    mathBytesTSpeed = np.array(list(bytesReceivedTimes.values()))
    
    bytesTime = go.Scatter(
        x =  mathBytesT,
        y =  mathBytesTSpeed ,
        name = 'Retrieved data'
    )
    
    layoutT = {
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : 'Comulative data retrieved (Chunks)',
        'yaxis' : dict(title='Size (KB)'),
        'xaxis' : dict(title='Time (s)'),
        'shapes': [],
        'showlegend' : True
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
                    'fillcolor': 'rgba(93, 191, 63, 0.2)',
                })
    
    dataTime = [bytesTime]
    figT = go.Figure(data=dataTime, layout=layoutT)
    htmlGraph = "<div>"
    htmlGraph += plot(figT , include_plotlyjs=includeLibrary, output_type='div')
    htmlGraph += "</div>"
    
    return htmlGraph

def graphSpeedTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData) :
    mathBytesTSec = np.array(list(bytesReceivedSecTimes.keys()))
    mathBytesTSecSpeed = np.array(list(bytesReceivedSecTimes.values()))
    mathBytesT = np.array(list(bytesReceivedTimes.values()))
    
    i = 0 
    for val in mathBytesT :
        if i > 0 :
            mathBytesT[i] = mathBytesT[i] / mathBytesTSec [i]
        else :
            mathBytesT[i] = mathBytesTSecSpeed[i]
        i += 1
    
    layoutT2 = {
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : 'Download speed (Chunks)',
        'yaxis' : dict(title='Speed (KB/s)'),
        'xaxis' : dict(title='Time (s)'),
        'shapes': [],
        'showlegend' : True
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
                    'fillcolor': 'rgba(93, 191, 63, 0.2)',
                })
    
    bytesTimeSec = go.Scatter(
        x =  mathBytesTSec,
        y =  mathBytesTSecSpeed ,
        name = 'Current speed'
    )
    
    bytesTime = go.Scatter(
        x =  mathBytesTSec,
        y =  mathBytesT ,
        name = 'Average speed'
    )
    
    dataTimeSec = [bytesTimeSec, bytesTime]
    figT2 = go.Figure(data=dataTimeSec, layout=layoutT2)
    htmlGraph = "<div>"
    htmlGraph += plot(figT2 , include_plotlyjs=includeLibrary, output_type='div')
    htmlGraph += "</div>"
    
    return htmlGraph

def graphPacketTime(packetSentSecTimes, packetReceivedSecTimes, wlanSegT, firstTimeDataMs, title) :
    times = np.array(list(packetSentSecTimes.keys()))
    
    sentL = np.array(list(packetSentSecTimes.values()))
    recL = np.array(list(packetReceivedSecTimes.values()))
    
    packetsSent = go.Scatter(
        x =  times,
        y =  sentL ,
        name = 'Sent packet'
    )
    
    packetsRec = go.Scatter(
        x =  times,
        y =  recL ,
        name = 'Received packet'
    )
    
    mean = go.Scatter(
        x = times,
        y = [str(sentL.mean() + recL.mean()) for i in range (0, len(times))],
        name = 'Mean'
    )
    
    layoutT = {
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : title,
        'shapes': [],
        'yaxis' : dict(title='Number of packets'),
        'xaxis' : dict(title='Time (s)'),
        'showlegend' : True
    }
    
    for seg in wlanSegT :
        if (seg[0] / 1e6) < firstTimeDataMs :
            startX = 0
        else :
            startX = ((seg[0] / 1e6) - firstTimeDataMs) / 1e3
            
        if (seg[1] / 1e6) < firstTimeDataMs :
            endX = 0
        else :
            endX = ((seg[1] / 1e6) - firstTimeDataMs) / 1e3
            
        if endX != 0 :
            layoutT['shapes'].append(
                {
                    'type': 'rect',
                    'x0': startX,
                    'y0': 0,
                    'x1': endX,
                    'y1': max((sentL.max() if sentL.size > 0 else 0 , recL.max() if recL.size > 0 else 0, sentL.mean() + recL.mean() if sentL.size > 0 and recL.size > 0 else 0)),
                    'line': {
                        'color': 'rgba(128, 0, 128, 0)',
                        'width': 2,
                    },
                    'fillcolor': 'rgba(93, 191, 63, 0.2)',
                })
    
    dataTime = [packetsSent, packetsRec, mean]
    figT = go.Figure(data=dataTime, layout=layoutT)
    htmlGraph = "<div>"
    htmlGraph += plot(figT, include_plotlyjs=includeLibrary, output_type='div')
    htmlGraph += "</div>"
    
    return htmlGraph

# def graphRtt(rtts, rttsMean) :
#     layoutT2 = {
#         'width' : str(graphWidth),
#         'height' : str(graphHeight),
#         'title' : 'Rtt strategy',
#         'shapes': []
#     }
#     
#     # for seg in wlanSegT :
#     #     if (seg[0] / 1e9) < firstTimeData :
#     #         startX = 0
#     #     else :
#     #         startX = (seg[0] / 1e9) - firstTimeData
#     #         
#     #     if (seg[1] / 1e9) < firstTimeData :
#     #         endX = 0
#     #     else :
#     #         endX = (seg[1] / 1e9) - firstTimeData
#     #         
#     #     if endX != 0 :
#     #         layoutT2['shapes'].append(
#     #             {
#     #                 'type': 'rect',
#     #                 'x0': startX,
#     #                 'y0': 0,
#     #                 'x1': endX,
#     #                 'y1': mathBytesTSecSpeed.max(),
#     #                 'line': {
#     #                     'color': 'rgba(128, 0, 128, 0)',
#     #                     'width': 2,
#     #                 },
#     #                 'fillcolor': 'rgba(93, 191, 63, 0.3)',
#     #             })
#     
#     gRtt = go.Bar(
#         x =  list(rtts.keys()),
#         y =  list(rtts.values()) ,
#         name = 'Rtt'
#     )
#     
#     gRttMean = go.Bar(
#         x =  list(rtts.keys()),
#         y =  list(rtts.values()) ,
#         name = 'Mean rtt'
#     )
#     
#     dataRtt = [gRtt, gRttMean]
#     figT2 = go.Figure(data=dataRtt, layout=layoutT2)
#     htmlGraph = "<div>"
#     htmlGraph += plot(figT2 , include_plotlyjs=includeLibrary, output_type='div')
#     htmlGraph += "</div>"
#     
#     return htmlGraph


def graphRttTime(rttTime, rttTimeMean, rttMin, rttMax, wlanSegT, firstTimeDataMs) :
    rttTimeMath = np.array([(r[0] / r[1]) for (i, r) in rttTime.items()])
    rttTimeMeanMath = np.array([(r[0] / r[1]) for (i, r) in rttTimeMean.items()])
    rttMinMath = np.array([(r[0] / r[1]) for (i, r) in rttMin.items()])
    rttMaxMath = np.array([(r[0] / r[1]) for (i, r) in rttMax.items()])
    
    
    layoutT2 = {
        'width' : str(graphWidth),
        'height' : str(graphHeight),
        'title' : 'RTT over time (Strategy)',
        'yaxis' : dict(title='RTT (ms)'),
        'xaxis' : dict(title='Time (s)'),
        'shapes': [],
        'showlegend' : True
    }
    
    for seg in wlanSegT :
        if (seg[0] / 1e6) < firstTimeDataMs :
            startX = 0
        else :
            startX = ((seg[0] / 1e6) - firstTimeDataMs) / 1e3
            
        if (seg[1] / 1e6) < firstTimeDataMs :
            endX = 0
        else :
            endX = ((seg[1] / 1e6) - firstTimeDataMs) / 1e3
            
        if endX != 0 :
            layoutT2['shapes'].append(
                {
                    'type': 'rect',
                    'x0': startX,
                    'y0': 0,
                    'x1': endX,
                    'y1': max((rttTimeMath.max() if rttTimeMath.size > 0 else 0, rttMaxMath.max() if rttMaxMath.size > 0 else 0, rttTimeMeanMath.max() if rttTimeMeanMath.size > 0 else 0, rttMinMath.max() if rttMinMath.size > 0 else 0)),
                    'line': {
                        'color': 'rgba(128, 0, 128, 0)',
                        'width': 2,
                    },
                    'fillcolor': 'rgba(93, 191, 63, 0.2)',
                })
    
    gRtt = go.Scatter(
        x =  [str(float(i / 10)) for (i, r) in rttTime.items()],
        y =  rttTimeMath,
        name = 'Estimated RTT'
    )
    
    gRttMean = go.Scatter(
        x =  [str(float(i / 10)) for (i, r) in rttTimeMean.items()],
        y =   rttTimeMeanMath,
        name = 'Retry timeout'
    )
    
    gRttMin = go.Scatter(
        x =  [str(float(i / 10)) for (i, r) in rttMin.items()],
        y =  rttMinMath,
        mode = 'markers',
        name = 'RTT below min'
    )
    
    gRttMax = go.Scatter(
        x =  [str(float(i / 10)) for (i, r) in rttMax.items()],
        y =  rttMaxMath,
        mode = 'markers',
        name = 'RTT over max'
    )
    
    #for (i, r) in rttTime.items() :
    #    print (str(r[0] / r[1]))
    
    
    dataRtt = [gRtt,gRttMean, gRttMin, gRttMax]
    figT2 = go.Figure(data=dataRtt, layout=layoutT2)
    htmlGraph = "<div>"
    htmlGraph += plot(figT2, include_plotlyjs=includeLibrary, output_type='div')
    htmlGraph += "</div>"
    
    return htmlGraph

def statToHtml(session, putStart, totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, mathDatasSent, bytesReceivedTimes, wlanSeg, wlanSegT, \
               firstTimeData, bytesReceivedSecTimes, usedStrategies, history, packetSentSecTimes, packetReceivedSecTimes, putPacketSent, putPacketRec, \
               rtts, rttsMean, rttTime, rttTimeMean, rttMin, rttMax, firstTimeDataMs) :
    
    file_count = len([f for f in os.listdir("results/") if os.path.isfile(os.path.join("results/", f))])

    resultsFile = open('results/' + str(file_count + 1) + '_' + str(session[0]['startTime']) + '_' + str(session[0]['id']) + '.html','w')
    
    resultsFile.write("""<!DOCTYPE html> <html> <head> <style> table { border-collapse: collapse; width: 100%; } th { text-align: center; padding: 8px; background-color: #CECCCC} td { text-align: left; padding: 8px; } tr:nth-child(even){background-color: #f2f2f2} " 
                      "table.address { border-collapse: collapse; width: 100%; } .address th { text-align: center; padding: 8px; background-color: #CECCCC} .address td { text-align: left; padding: 8px; } .address tr:nth-child(even){background-color: #f2f2f2}</style> </head> <body>""")
    
    # T T   C
    #  C    C

    resultsFile.write("<div style = 'float: left'>")
    
    resultsFile.write("<div style = 'width: 100%'>")
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(tableInput(session, putStart))
    resultsFile.write("</div>")
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(tableResults(totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, usedStrategies))
    resultsFile.write("</div>")
    resultsFile.write("</div>")
    
    
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(graphPacketTime(packetSentSecTimes, packetReceivedSecTimes, wlanSegT, firstTimeDataMs, "Consumer packets (Socket)"))
    includeLibrary = False
    resultsFile.write(graphPacketTime(putPacketSent, putPacketRec, wlanSegT, firstTimeDataMs, "Producer packets (Socket)"))
    resultsFile.write("</div>")
    resultsFile.write("</div>")
    
    resultsFile.write("<div>")
    resultsFile.write("<div style = 'float: left'>")
    #resultsFile.write(graphRtt(rtts, rttsMean))
    resultsFile.write(graphRttTime(rttTime,rttTimeMean, rttMin, rttMax, wlanSegT, firstTimeDataMs)) 
    resultsFile.write("</div>")
    
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(graphBytesTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData)) 
    resultsFile.write(graphSpeedTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData))
    resultsFile.write("</div>")
    
    
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(graphTimesSegments(mathTimes, wlanSeg))
    resultsFile.write(graphTimeoutSegments(mathTimeout, mathDatasSent, wlanSeg))
    resultsFile.write("</div>")
    
    
    resultsFile.write("<div style = 'float: right'>")
    resultsFile.write(tableHistory(history))
    resultsFile.write("</div>")
    
    
    resultsFile.write("</div>")
    

    resultsFile.close()
    
    print("Results written to: " + resultsFile.name)
    

