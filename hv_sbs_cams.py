########################################################
##Created: 01/24/2025
##Updated: 10/07/2022 by Deon T
##Descr: Runs a camera that connects to the PLC looking for errors.
##       
## _Classes_
## camras()
## OakVideoStream()
########################################################
import cv2
import depthai as dai
import io

import collections
import datetime
import inspect
import os
import sys
import time

import traceback

  ########################################################
  ### runthecamera()
  ########################################################
class runthecamera:
  def __init__(self, camident,camindex,localfaultdetected,infoqueue,timetostop):
    self.camident = camident
    self.camindex = camindex
    self.localfaultdetected = localfaultdetected
    self.infoqueue = infoqueue
    self.timetostop = timetostop
    
    self.run()
    
  def run(self):
    try:
      self.infoqueue.append(["Starting Camera"+str(self.camindex)+".",False,1])
      pipeline = None
      camRgb = None
      xlinkOut = None
      xoutRgbD = None #display
      str_outD = "display"

      codec = "mjpeg"

      rollingvid = collections.deque()
      stopped = False

      pipeline = dai.Pipeline()
      camRgb = pipeline.create(dai.node.ColorCamera)
      xoutRgbD = pipeline.create(dai.node.XLinkOut)

      xoutRgbD.setStreamName(str_outD)

      camRgb.setPreviewSize(320,320)
      camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
      camRgb.setIspScale(1,3)
      camRgb.setPreviewKeepAspectRatio(False)
      
      xoutRgbD.input.setBlocking(False)
      xoutRgbD.input.setQueueSize(1)

      camRgb.video.link(xoutRgbD.input)
      
      colorforbad = (0,0,250) # bad detects
      colorforframe = (150, 250, 100) # debug frames
      colorforgood = (250,255,250) # good detects
      colorfortext = (0,85,204) # for text writing.
      colorforblack = (0,0,0)
      colorforwhite = (255,255,255)    
      
      frametimestamps = collections.deque()
      rollingfps = 0
      rollingtimer = 0
      
      starttime = time.perf_counter()
      appstart = time.time()
      alreadydone = False
      
      with dai.Device(pipeline,self.camident) as device:
        displayer = device.getOutputQueue(name=str_outD, maxSize=1, blocking=False)    

        firsttimethrough = 0

        while not self.timetostop[0]:
          theframe = displayer.get().getCvFrame()
          cv2.rectangle(theframe,(0,0),(210,20),(0,0,0),-1)
          cv2.putText(theframe,"C"+str(self.camindex)+" "+str(datetime.datetime.now()).split(".")[0], (5, 15), cv2.FONT_HERSHEY_SIMPLEX, .5, colorforwhite, thickness=1)

          if firsttimethrough == 0:
            firsttimethrough += 1
          elif firsttimethrough == 1:
            awidth, aheight,achannel = theframe.shape
            firsttimethrough += 1

          ## Time stuff
          frametimestamps.append(time.perf_counter())
          rollingvid.append(theframe)
          #self.infoqueue.append(["C"+str(self.camindex)+" trying .imshow.",False,2])
          #cv2.imshow("Camera_"+str(self.camindex), theframe)
          
          ## Maintain rolling video at 30 seconds.
          totaltime = (frametimestamps[-1]-frametimestamps[0])
          if totaltime > 30:
            rollingfps = int((len(frametimestamps)/totaltime))
            for i in range(int((totaltime-30)*rollingfps)):
              rollingvid.popleft()
              frametimestamps.popleft()
          cv2.waitKey(1)

          ## Video to capture
          if self.localfaultdetected[0] and not alreadydone:
            #self.infoqueue.append(["C"+str(self.camindex)+" has detected a fault and hasn't saved yet.",False,1])
            alreadydone = True
            rollingfps = int((len(frametimestamps)/(frametimestamps[-1]-frametimestamps[0])))
            
            # Define the codec and create VideoWriter object.The output is stored in 'outpy.avi' file.
            thatfilename = str(datetime.datetime.now()).replace(" ","_").replace(":","").replace("-","").split(".")[0]+"_camra"+str(self.camindex)+"_"+str(firsttimethrough).zfill(3)+"_"+str(rollingfps)+"fps.avi"
            self.infoqueue.append(["Writing: "+thatfilename+" at "+str(rollingfps)+" fps/("+str(str(len(rollingvid)))+" frames).",False,3])
            outvid = cv2.VideoWriter(thatfilename,cv2.VideoWriter_fourcc(*'MPEG'), rollingfps, (aheight,awidth))
            firsttimethrough += 1

            for jpo in rollingvid:
              outvid.write(jpo)
            outvid.release()
            self.localfaultdetected[2] += 1
            #self.infoqueue.append(["C"+str(self.camindex)+" "+str(self.localfaultdetected)+".",False,2])
            if self.localfaultdetected[2] >= self.localfaultdetected[1]:
              self.localfaultdetected[2] = 0
              self.localfaultdetected[0] = False
          if not self.localfaultdetected[0] and alreadydone:
            #self.infoqueue.append(["C"+str(self.camindex)+" has detected a fault but has already saved.",False,1])
            alreadydone = False

      self.infoqueue.append(["OakcamVideoStream"+str(self.camindex)+" has ended.",False,3])
      try:
        self.infoqueue.append(["Closing Camera"+str(self.camindex)+".",False,3])
        device.close()
      except Exception as exception:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
        self.infoqueue.append(["Camera"+str(self.camindex)+" stop failed: "+errorstring+"</b>",False,3])  
    except Exception as exception:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
      self.infoqueue.append(["Camera"+str(self.camindex)+" stop failed: "+errorstring+"</b>",False,3])  
      self.localfaultdetected[1] -= 1
      if self.localfaultdetected[2] >= self.localfaultdetected[1]:
        self.localfaultdetected[2] = 0
        self.localfaultdetected[0] = False
