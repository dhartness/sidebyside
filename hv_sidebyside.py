########################################################
##Created: 01/24/2025
##Updated: 10/07/2022 by Deon T
##Descr: Runs a camera that connects to the PLC looking for errors.
##       
## _Classes_
## camras()
## OakVideoStream()
########################################################

import hv_sbs_cams

import collections
import cv2
import datetime
import depthai as dai
import inspect
import multiprocessing
import numpy as np
import os
from pycomm3 import LogixDriver
import sys
import random
import threading
import time
import traceback

import logging
import logging.handlers
import logging.config
from vlogging import VisualRecord

import io

########################################################
###  Class: camfaultcatcher()
###  Purpose: A wrapper for the camera classes
###  Arguments: typeoflens - Which camera to start, use the dictionary
###  Wants: Need to clean this up and experiment with the available streams.
########################################################
class camfaultcatcher:
  def __init__(self):
    
    self.guithere = True
    try:
        import tkinter as tk
        gravy = "GUI is available"
    except ModuleNotFoundError:
      self.guithere = False
      gravy = "GUI is not available."
    print(gravy) 
    self.dostop = [False]
    self.faultdetected = [False,0,0] # is fault,maxcams,completevidsaves
    self.printlogqueue = collections.deque() # [string,onlylog=F,level(1=info,2=warn,3=error,4=debug)=1]
    self.printlogqueue.append([gravy,True,1])
    self.anewcamera = []
    self.logprint = None
    self.plccomms = None
    
    self.run()

  ########################################################
  ### run()
  ########################################################
  def run(self):
    try:
      maxcamerawait = 30 # seconds until timeout.
      howlonguntilwait = time.perf_counter()
      camimgrepos = [None]
      camerasfound = False
      try:
        if os.path.exists("logly.stop"):
          os.rename("logly.stop","logly.go")
        elif not os.path.exists("logly.go"):
          with open("logly.go",'w') as fp:
            pass
      except Exception as exception:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
        print(errorstring)
        self.printlogqueue.append(errorstring,False,3)

      self.logprint = threading.Thread(target=self.printlogger, args=(self.printlogqueue,self.dostop),name="logger and printer", daemon=True).start()
      self.plccomms = threading.Thread(target=self.runtheplccom,args=(self.faultdetected,self.printlogqueue,self.dostop),name="plccommunication", daemon=True).start()
      
      while (not camerasfound) and ((time.perf_counter() - howlonguntilwait) < maxcamerawait):
        devices = dai.Device.getAllAvailableDevices()
        self.faultdetected[1] = len(devices)
        self.anewcamera = [None]*len(devices)
        camimgrepos = [None]
        camimgrepos[0] = [None]*len(devices)
        self.printlogqueue.append(["Detected "+str(len(devices))+" cameras.",False,1])
        print(camimgrepos)
        if len(devices) > 0:
          camerasfound = True
        else:
          self.printlogqueue.append(["No cameras found after "+str(int(time.perf_counter()-howlonguntilwait))+" seconds.",False,2])
          time.sleep(.1)
      if not camerasfound:
        self.dostop[0] = True
      for j in range(len(devices)):
        self.anewcamera[j] = threading.Thread(target=hv_sbs_cams.runthecamera, args=(devices[j],(j+1),camimgrepos[0],self.faultdetected,self.printlogqueue,self.dostop),name="the cameras", daemon=True).start()
        # time.sleep(5)
      ## ###############################################################################
      ## The display grid layout.
      minmatrix = [(213,120),(160,90)]
      scalefactor = 3 if (len(devices) < 10) else 4
      smallier = [None]*(scalefactor*scalefactor)
      rowed = [None]*scalefactor
      ttempt = None
      finalstitch = None
      ## ###############################################################################
      while not self.dostop[0]:
        ## ###############################################################################
        ## Display
        # print(camimgrepos)
        for v in range(len(devices)):
          if len(camimgrepos[0][v]):
            ttempt = camimgrepos[0][v][0]
          else:
            ttempt = np.zeros((minmatrix[scalefactor-3][1],minmatrix[scalefactor-3][0],3), np.uint8)
          try:
            smallier[v] = cv2.resize(ttempt,(minmatrix[scalefactor-3][0],minmatrix[scalefactor-3][1]))
          except Exception as exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
            self.printlogqueue.append(["resize attempt "+str(v)+"-"+errorstring,False,3])
          if len(smallier[v].shape) != 3:
            smallier[v] = cv2.merge([smallier[v],smallier[v],smallier[v]])
        # Creating the remaining non-existing camera feeds.
        for jm in range(len(devices), len(smallier)):
          smallier[jm] = np.zeros((minmatrix[scalefactor-3][1],minmatrix[scalefactor-3][0],3), np.uint8)
        for out in range(scalefactor):
          if scalefactor == 3:
            rowed[out] = np.hstack((smallier[out*scalefactor],smallier[out*scalefactor+1],smallier[out*scalefactor+2]))
          elif scalefactor == 4:
            rowed[out] = np.hstack((smallier[out*scalefactor],smallier[out*scalefactor+1],smallier[out*scalefactor+2],smallier[out*scalefactor+3]))
        if scalefactor == 3:
          finalstitch = np.vstack((rowed[0],rowed[1],rowed[2]))
        elif scalefactor == 4:
          finalstitch = np.vstack((rowed[0],rowed[1],rowed[2],rowed[3]))
        cv2.imshow("Camera Feed", finalstitch)
          ###########***************************************************
          # if camimgrepos[0][v]:
            # cv2.imshow("Camera_"+str(v+1),camimgrepos[0][v])
          ###########***************************************************
       
        ## ###############################################################################
        if os.path.exists("logly.stop"):
          self.printlogqueue.append(["Found logly.stop. Will rename and then shutdown threads.",False,1])
          os.rename("logly.stop","logly.go")
          self.dostop[0] = True
          time.sleep(1)
      time.sleep(.1)
    except Exception as exception:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
      print(errorstring)
      self.printlogqueue.append(["<b>Machine stop failed: "+errorstring+"</b>",False,3])

  ########################################################
  ### isAlive()
  ########################################################
  # def isAlive(self):
    # return self.thecamera.is_alive()

  ########################################################
  ### printlogger()
  ########################################################
  def printlogger(self,infoqueue,timetostop):
    try:
      # [string,onlylog=F,level(1=info,2=warn,3=error,4=debug)=1]
      logging.basicConfig(
        format='%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s', level=logging.INFO,
        handlers=[logging.handlers.RotatingFileHandler("sidebyerr.log", mode='a', maxBytes=5242880, backupCount=10)])
      while not timetostop[0] or not infoqueue:# To clear out the print queue.
        if infoqueue:
          rtw = infoqueue.popleft()
          if rtw[2] == 1:
            logging.info(rtw[0])
          elif rtw[2] == 2:
            logging.warning(rtw[0])
          elif rtw[2] == 3:
            logging.error(rtw[0])
          elif rtw[2] == 4:
            logging.debug(rtw[0])
          if not rtw[1]:
            print(rtw[0])
        time.sleep(.1)
      print("Exiting printlogger.")
    except Exception as exception:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
      print(errorstring)
      # infoqueue.append(["<b>Machine stop failed: "+errorstring+"</b>",False,3])    

  ########################################################
  ### runthefakecom()
  ########################################################
  def runthefakecom(self, localfaultdetected,infoqueue,timetostop):
    try:
      starttime = time.perf_counter()
      maxruntime = 300
      
      #random video intervals
      fakeevent = time.perf_counter()
      randvidint = random.randint(15,40)
      infoqueue.append(["Next Time Until Fault: "+str(randvidint),False,2])

      while not timetostop[0]:
        if (time.perf_counter() - starttime) > maxruntime:
          infoqueue.append(["Maxtime reached for text loop. Laters!",False,2])
          #timetostop[0] = True
          break
        if (time.perf_counter()-fakeevent) > randvidint:
          localfaultdetected[0] = True
          fakeevent = time.perf_counter()
          randvidint = random.randint(35,90)
          infoqueue.append(["Next Time Until Fault: "+str(randvidint),False,2])
          while localfaultdetected[0]:
            time.sleep(.1)
    except Exception as exception:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
      infoqueue.append(["<b>Machine stop failed: "+errorstring+"</b>",False,3])    

  ########################################################
  ### runtheplccom()
  ########################################################
  def runtheplccom(self, localfaultdetected,infoqueue,timetostop):
    plcaddy = "192.168.1.1"
    plcsc = None
    PLCavailable = False
    internaltimewait = 0
    try:
      while not timetostop[0]:
        internaltimewait = time.perf_counter()
        while True: #Make the connection.
          plcsc = LogixDriver(plcaddy,init_tags=True)
          try:
            PLCavailable = plcsc.open()
          except Exception as exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
            infoqueue.append(["<b>Machine stop failed: "+errorstring+"</b>",False,3])    
          if PLCavailable:
            infoqueue.append(["Connected to PLC.",False,1])
            break
          else:
            infoqueue.append(["Failed to connect to PLC.",False,3])
            if (time.perf_counter() - internaltimewait) > 30:
              break
            time.sleep(1)
        if PLCavailable:
          while not timetostop[0]:
            try:
              if not localfaultdetected[0]:
                localfaultdetected[0] = bool(plcsc.read("ResetPushbutton").value)
                if localfaultdetected[0]:
                  infoqueue.append(["Fault detected. Hopefully will capture video.",False,1])
              time.sleep(.1)
            except Exception as exception:
              exc_type, exc_obj, exc_tb = sys.exc_info()
              errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
              infoqueue.append(["Reading from PLC: "+errorstring+"</b>",False,3])
        else:
          infoqueue.append(["Running testing loop in absense of PLC connection.",False,3])
          self.runthefakecom(localfaultdetected,infoqueue,timetostop)
    except Exception as exception:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      errorstring = str(inspect.stack()[0][3])+" - "+str(exc_type)+" on l#"+str(exc_tb.tb_lineno)+": "+str(exception)
      infoqueue.append(["PLC Connection: "+errorstring+"</b>",True,3])    

  ########################################################
  ### stop()
  ########################################################
  def stop(self,timetostop):
    # self.logging.info("Trying to stop camfaultcatcher.")
    self.stopped = True

#****************************************************
if __name__  ==  '__main__':
  camfaultcatcher()
