import sys
import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
import datetime

import os

def timestampToDate(timestamp) :
    return  datetime.datetime.fromtimestamp(timestamp / 1e9).strftime('%Y-%m-%d %H:%M:%S')

def tableInput(ses) :
    errorString = 'Yes'
    if (ses[0]['exitCode'] != 0) :
            errorString = 'No'
    
    stat = []
    stat.append((' Input parameters ', -1))
    stat.append(('Started : ', timestampToDate(ses[0]['timestamp'])))
    stat.append(('Finished : ', timestampToDate(ses[1])))
    stat.append(('Completed: ', errorString ))
    stat.append(('Duration (s) :', (ses[1] - ses[0]['timestamp']) / 1000000000))
    stat.append(('Max Pipeline size : ', str(ses[0]['maxPipelineSize'])))
    stat.append(('Interest lifetime (ms) : ', str(ses[0]['interestLifetime'])))
    stat.append(('Max retries  : ', str(ses[0]['maxRetries'])))
    stat.append(('Must be fresh : ', str(ses[0]['mustBeFresh'])))
    
    htmlStat = "<div><table>"
    for value in stat :
        if value[1] == -1 : #TODO very bad 
            htmlStat += "<tr><th colspan='2'>" + value[0] + "</th></tr>"
        else:
            htmlStat += "<tr><td>" + value[0] + "</td><td>" + str(value[1]) + "</td></tr>"
    htmlStat += "</table></div>"
    
    return htmlStat

def tableResults(totTime, segmentsDic, mathBytes, mathTimes, mathTimeout) :
    stat = []
    stat.append(('Overall', -1))
    stat.append(('Total time (s) : ', totTime))
    stat.append(('Number of segments : ', len(segmentsDic)))
    stat.append(('Total received data (MB): ', mathBytes.sum()/1000000))
    stat.append(('Speed (KB/s) : ', (mathBytes.sum()/1000)/totTime))
    stat.append(('Retrieve times ', -1))
    stat.append(('Min (ms) : ', mathTimes.min()/ 1000000))
    stat.append(('Max (ms) : ', mathTimes.max()/ 1000000))
    stat.append(('Mean (ms) : ', mathTimes.mean()/ 1000000))
    stat.append(('Dev. std. (ms) : ', mathTimes.std()/ 1000000))
    stat.append(('Timeouts', -1))
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


def graphTimesSegments(mathTimes, wlanSeg) :
    trace1 = go.Scatter(
        x = list(range(0, len(mathTimes) - 1)),
        y = mathTimes / 1000000,
        name = 'Segment retrieval time'
    )
    
    mean = go.Scatter(
        x = list(range(0, len(mathTimes) - 1)),
        y = [str(mathTimes.mean() / 1000000) for i in range (0, len(mathTimes) - 1)],
        name = 'Mean'
    )
    
    layout = {
        'autosize' : 'false',
        'yaxis' : dict(range=[0, (mathTimes.mean() / 1000000) * 2]),
        'width' : '800',
        'height' : '600',
        'title' : 'Retrieve time (s) for each segment',
        'shapes': []
    }
    
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
        
    data = [trace1, mean]
    fig = go.Figure(data=data, layout=layout)
    
    htmlGraph = "<div>" #style = 'float: left'
    htmlGraph += plot(fig , output_type='div', include_plotlyjs='true')
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
        'width' : '800',
        'height' : '550',
        'title' : 'Retrived Data (KB)',
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
    htmlGraph = "<div>"
    htmlGraph += plot(figT , include_plotlyjs='false', output_type='div')
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
        i += 1
    
    layoutT2 = {
        'width' : '800',
        'height' : '550',
        'title' : 'Download speed (KB/s)',
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
    htmlGraph += plot(figT2 , include_plotlyjs='false', output_type='div')
    htmlGraph += "</div>"
    
    return htmlGraph

def statToHtml(session, totTime, segmentsDic, mathBytes, mathTimes, mathTimeout, bytesReceivedTimes, wlanSeg, wlanSegT, firstTimeData, bytesReceivedSecTimes) :  

    resultsFile = open('res_' + str(session[0]['startTime']) + '.html','w')
    
    resultsFile.write("<!DOCTYPE html> <html> <head> <style> table { border-collapse: collapse; width: 100%; } th, td { text-align: left; padding: 8px; } tr:nth-child(even){background-color: #f2f2f2} </style> </head> <body>")
    
    # T T   C
    #  C    C

    resultsFile.write("<div style = 'float: left'>")
    
    resultsFile.write("<div>")
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(tableInput(session))
    resultsFile.write("</div>")
    resultsFile.write("<div style = 'float: right'>")
    resultsFile.write(tableResults(totTime, segmentsDic, mathBytes, mathTimes, mathTimeout))
    resultsFile.write("</div>")
    resultsFile.write("</div>")
    
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(graphTimesSegments(mathTimes, wlanSeg))
    resultsFile.write("</div>")
    resultsFile.write("</div>")
    
    resultsFile.write("<div style = 'float: left'>")
    resultsFile.write(graphBytesTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData)) 
    resultsFile.write(graphSpeedTime(bytesReceivedTimes, bytesReceivedSecTimes, wlanSegT, firstTimeData))
    resultsFile.write("</div>")
    

    resultsFile.close()
    
    print("Results written to: " + resultsFile.name)
    

