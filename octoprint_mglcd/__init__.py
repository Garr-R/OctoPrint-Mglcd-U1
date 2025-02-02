
import serial
import time
import sys
import threading
import traceback
import re
import sched
import socket
import array
import glob
import copy
import math
import datetime
import os
import shutil
from numbers import Number
from threading import Thread
from multiprocessing import Process
from octoprint.filemanager.destinations import FileDestinations
from collections import deque
from collections import defaultdict
from collections import OrderedDict
import octoprint.filemanager
import octoprint.filemanager.util
import octoprint.filemanager.storage
import octoprint.slicing
from octoprint.server import printer, fileManager, slicingManager, eventManager, NO_CONTENT
from flask import jsonify, make_response
import logging
from octoprint.server import admin_permission
import json


### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin


class Component(object):

	def __init__(self,page,id,name):
		self.page=page
		self.id=id
		self.name=name

	@staticmethod
	def newComponentByDefinition(page, componentDefinition):
		type=componentDefinition['type']
		id=componentDefinition['id']
		name=None
		name=componentDefinition['name']
		value=None
		try:
			value=componentDefinition['value']
		except KeyError:
			pass

		if "text" in type:
			return Text(page,id,name,value)
		elif "number" in type:
			return Number(page,id,name,value)
		elif "button" in type:
			return Button(page,id,name,value)
		elif "gauge" in type:
			return Gauge(page,id,name,value)
		elif "hotspot" in type:
			return HotSpot(page,id,name)
		elif "waveform" in type:
			return WaveForm(page,id,name)
		
		return None

class Text(Component):

	def __init__(self,page,id,name=None,value=None):
		super(Text, self).__init__(page,id,name)
		if value is not None:
			self.page.nextion.setText(self.id,value)

	def get(self):
		return self.page.nextion.getText(self.id)

	def set(self,value):
		self.page.nextion.setText(self.id,value)

class Number(Component):

	def __init__(self,page,id,name=None,value=None):
		super(Number, self).__init__(page,id,name)
		if value is not None:
			self.page.nextion.setValue(self.id,value)

	def get(self):
		return self.page.nextion.getValue(self.id)

	def set(self,value):
		self.page.nextion.setValue(self.id,value)

class Button(Component):

	def __init__(self,page,id,name=None,value=None):
		super(Button, self).__init__(page,id,name)
		if value is not None:
			self.page.nextion.setText(self.id,value)

	def get(self):
		return self.page.nextion.getText(self.id)

	def set(self,value):
		self.page.nextion.setText(self.id,value)

class HotSpot(Component):

	def __init__(self,page,id,name=None):
		super(HotSpot, self).__init__(page,id,name)

class WaveForm(Component):

	def __init__(self,page,id,name=None):
		super(WaveForm, self).__init__(page,id,name)

	def add(self,channel, value):
		print(str(self.id)+":"+str(channel)+" => "+str(value))
		self.page.nextion.nxWrite("add " + self.id + "," + channel + "," + value)

class Gauge(Component):

	def __init__(self,page,id,name=None,value=None):
		super(Gauge, self).__init__(page,id,name)
		if value is not None:
			self.page.nextion.setValue(self.id,value)

	def get(self):
		return self.page.nextion.getValue(self.id)

	def set(self,value):
		self.page.nextion.setValue(self.id,value)

class Page(object):
	def __init__(self, nextion,id):
		self.components=[]
		self.id=id
		self.name=None
		self.nextion=nextion

	@staticmethod
	def newPageByDefinition(nextion,pageDefinition):
		page=Page(nextion,pageDefinition['id'])
		page.name=pageDefinition['name']
		if pageDefinition['components'] is not None:
				for componentDefinition in pageDefinition['components']:
					page.components.append(Component.newComponentByDefinition(page,componentDefinition))
		return page
		
	
	def componentByName(self,name):
		result=None
		for component in self.components:
			if name == component.name:
				result=component
				break
		return result

	def hookText(self,id,value=None):
		component=Text(self,id,value)
		self.components.append(component)
		return control

	def show(self):
		self.nextion.setPage(self.id)

class Nextion(object):

	ERRORS={
		"00": "Invalid instruction",
		"01": "Successful execution of instruction",
		"03": "Page ID invalid",
		"04": "Picture ID invalid",
		"05": "Font ID invalid",
		"11": "Baud rate setting invalid",
		"12": "Curve control ID number or channel number is invalid",
		"1a": "Variable name invalid",
		"1b": "Variable operation invalid"
	}

	MESSAGES={
		"65": "Touch event return data",
		"66": "Current page ID number returns"
	}

	RED   =63488	
	BLUE  =31	
	GRAY  =33840	
	BLACK =0	
	WHITE =65535	
	GREEN =2016	
	BROWN =48192
	YELLOW=65504

	def __init__(self,ser,pageDefinitions=None):
		print("Nextion initializing.")
		self.pages = []
		self.debug = False
		self.ser = ser
		while True:
			if self.debug:
				print("in init whileTrue loop")
			try:
				if self.debug:
					print("in init whileTrue loop - trying")
				# self.setBkCmd(3)
				break
			except:
				print("Wait...")
				if self.debug:
					print("in init whileTrue loop - exception")
				time.sleep(1)

		if pageDefinitions is not None:
			for pageDefinition in pageDefinitions:
					self.pages.append(Page.newPageByDefinition(self,pageDefinition))


	def pageByName(self,name):
		result=None
		for page in self.pages:
			if page.name == name:
				result=page
				break
		return result

	def hookPage(self,id):
		page=Page(self,id)
		self.pages.append(page)
		return page

	def setDebug(self,debug):
		self.debug=debug

	def setBkCmd(self,value):
		if self.debug:
			print("nextion - setBkCmd")
		self.set('bkcmd',value)

	def setDim(self,value):
		self.set('dim',value)

	def setDim(self,value):
		self.set('dims',value)

	def setPage(self,value):
		s=self.nxWrite('page '+str(value))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0])+": page "+str(value))

	def getPage(self):
		self.ser.flushOutput()
		s=self.nxWrite('sendme')
		if s[0]==0x66:
				if s[1]==0xff: s[1]=0x00
				return s[1]

		raise ValueError(Nextion.getErrorMessage(0x00))



	def refresh(self,id="0"):
		s=self.nxWrite('ref %s' % id)
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def getText(self,id):
		s=self.nxWrite('get %s.txt' % id)
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def getValue(self,id):
		s=self.nxWrite('get %s.val' % id)
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def setValue(self,id,value):
		print(id+'.val="'+str(value)+'"')
		s=self.nxWrite(id+'.val='+str(value))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0])+": id: "+id+" value:"+ value)

	def setText(self,id,value):
		s=self.nxWrite(id+'.txt="'+str(value)+'"')
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0])+": id: "+id+" text:"+ value)

	def clear(self,color):
		s=self.nxWrite('cls %s' % color);
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawPicture(self,x,y,pic,w=None,h=None):
		if w is None or h is None:
			s=self.nxWrite('pic %s,%s,%s' % (x,y,pic))
		else:
			s=self.nxWrite('picq %s,%s,%s,%s,%s,%s' %(x,y,pic,w,h))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawString(self,x1,y1,x2,y2,fontid,fontcolor,backcolor,xcenter,ycenter,sta,string):
		s=self.nxWrite('xstr %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (x1,y1,x2-x1,y2-y1,fontid,fontcolor,backcolor,xcenter,ycenter,sta,string))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawLine(self,x1,y1,x2,y2,color):
		s=self.nxWrite('line %s,%s,%s,%s,%s' % (x1,y1,x2,y2,color))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawRectangle(self,x1,y1,x2,y2,color):
		s=self.nxWrite('draw %s,%s,%s,%s,%s' % (x1,y1,x2,y2,color))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawBox(self,x1,y1,x2,y2,color):
		s=self.nxWrite('fill %s,%s,%s,%s,%s' % (x1,y1,x2-x1,y2-y1,color))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))

	def drawCircle(self,x,y,r,color):
		s=self.nxWrite('cir %s,%s,%s,%s' % (x,y,r,color))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0]))


	def set(self,key,value):
		if self.debug:
			print("nextion - set")
		s=self.nxWrite(key+'='+str(value))
		if s[0]!=0x01:
			raise ValueError(Nextion.getErrorMessage(s[0])+": "+key+"="+str(value))
		

	@staticmethod
	def getErrorMessage(s):
		 return Nextion.ERRORS[format(s, '02x')]

	def nxWrite(self,s):
		if self.debug:
			print("nextion - nxWrite")
		# self.ser.write(s)
		# self.ser.write(chr(255))
		# self.ser.write(chr(255))
		# self.ser.write(chr(255))
		self.ser.write(s.encode("latin1", "backslashreplace"))
		self.ser.write(b"\xFF\xFF\xFF")
		# return self.nxRead()

	def nxRead(self,cmax=0,timeout=0.5):
		if self.debug:
			print("nextion - nxRead")
		s=[]
		done=False
		def _reader():
			count=0
			time_now = time.clock()
			while timeout==0 or (time.clock()-time_now)<timeout:
				if self.debug:
					print("nextion - nxRead loop, while timeout==0 etc...")
				try:
					r = self.ser.read()
					if r is None or r=="":
						continue

					c = ord(r)
					if c==0xff and len(s)==0:
						continue

					if c!=0x00:        
						if self.debug is True:
							print("\/ :"+str(c)+":"+str(len(s))+":"+str(count))

						s.append(c)
						if len(s)==cmax:
							return
						if c==0xff:
							count=count+1
							if count==3:
								if self.debug is True:
									print("!!")
								return
						# elif c==0x0A:
						# 	count=0
						# 	s.append(c)
						# 	# NextionPlugin.processMessage(s)
						# 	return
						else:
							count=0
						if self.debug is True:
							print("/\ :"+str(c)+":"+str(len(s))+":"+str(count))
				except:
					# self._logger.info(err)
					# self._logger.info("Error when reading!")
					print("Error when reading")
			print("Timeout")
			if self.debug:
				print("nextion - timeout in nxRead")

		if self.debug:
			print("nextion - broke out of _reader loop without error.")
		if self.debug:
			print(s)
		t = Thread(target=_reader)
		t.start()
		t.join()
		return s 

class NextionPlugin(octoprint.plugin.StartupPlugin,
						octoprint.plugin.TemplatePlugin,
						octoprint.plugin.SettingsPlugin,
						octoprint.plugin.AssetPlugin,
						octoprint.plugin.SimpleApiPlugin,
						octoprint.plugin.EventHandlerPlugin,
						octoprint.printer.PrinterCallback,
						octoprint.plugin.ShutdownPlugin):

	##~~ SettingsPlugin mixin

	def __init__(self):
		self.receiveLog = deque([])
		self.logLock = threading.Lock()
		# self.displayConnection
		self.displayConnected = False
		self.tryToConnect = True

		self.commFails = 0
		self.connectionFails = 0
		self.connectionMaxTimeBetween = 20
		self.displayConnectionTimer = octoprint.util.RepeatedTimer(self.interval, self.connect_to_display)
		self.serialReceiveTimer = octoprint.util.RepeatedTimer(0.05, self.nextionTimer, daemon=True)
		self.serialParseTimer = octoprint.util.RepeatedTimer(0.1, self.parseLog, daemon=True)
		self.ipTimer = octoprint.util.RepeatedTimer(120, self.populateIpAddress)
		self.currentPage = ''
		self.files = {}
		self.deleteFiles = {}
		self.fileList = defaultdict(list)
		self.wifiList = defaultdict(list)
		self.deleteList = defaultdict(list)
		self.currentFolder = ''
		self.currentPath = ''
		self.previousFolderList = []
		self.filamentInFile = 0.0
		self.fileListLocation = 0
		self.deleteListLocation = 0
		self.wifiListLocation = 0
		self.connectedPort = ''
		self.flashingFirmware = False
		self.firmwareFlashingProgram = ""
		self.firmwareLocation = ""
		self.buttonPressCount = 0
		self.address = None
		self.chosenSsid = ""
		self.pendingAction = ""
		self.confirmRequired = True
		self.waitingForConfirm = False
		self.rrf = True
	
	def initialize(self):
		self.address = self._settings.get(["socket"])

	@property
	def hostname(self):
		hostname = self._settings.get(["hostname"])
		if hostname:
			return hostname
		else:
			import socket
			return socket.gethostname() + ".local"

	def serial_ports(self):
		# With all credit to SO Thomas.
		""" Lists serial port names

			:raises EnvironmentError:
				On unsupported or unknown platforms
			:returns:
				A list of the serial ports available on the system
		"""
		if sys.platform.startswith('win'):
			ports = ['COM%s' % (i + 1) for i in range(256)]
		elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
			# this excludes your current terminal "/dev/tty"
			ports = glob.glob('/dev/ttyUSB*')
		elif sys.platform.startswith('darwin'):
			ports = glob.glob('/dev/ttyUSB.*')
		else:
			raise EnvironmentError('Unsupported platform')

		result = []
		for port in ports:
			try:
				s = serial.Serial(port)
				s.close()
				result.append(port)
			except (OSError, serial.SerialException):
				pass
		return result

	def _to_unicode(self, s_or_u, encoding="utf-8", errors="strict"):
		"""Make sure ``s_or_u`` is a unicode string."""
		if isinstance(s_or_u, str):
			return s_or_u.decode(encoding, errors=errors)
		else:
			return s_or_u


	def _execute(self, command, **kwargs):
		import sarge

		if isinstance(command, (list, tuple)):
			joined_command = " ".join(command)
		else:
			joined_command = command
		#_log_call(joined_command)

		# kwargs.update(dict(async=True, stdout=sarge.Capture(), stderr=sarge.Capture()))

		try:
			p = sarge.run(command, async_=True, stdout=sarge.Capture(), stderr=sarge.Capture())
			while len(p.commands) == 0:
				# somewhat ugly... we can't use wait_events because
				# the events might not be all set if an exception
				# by sarge is triggered within the async process
				# thread
				time.sleep(0.01)

			# by now we should have a command, let's wait for its
			# process to have been prepared
			p.commands[0].process_ready.wait()

			if not p.commands[0].process:
				# the process might have been set to None in case of any exception
				#print("Error while trying to run command {}".format(joined_command), file=sys.stderr)
				# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = "Error while trying to run command - 1."))
				# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = p.stderr.readlines(timeout=0.5)))
				# self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = p.stdout.readlines(timeout=0.5)))
				return None, [], []
		except:
			#print("Error while trying to run command {}".format(joined_command), file=sys.stderr)
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = "Error while trying to run command - 2."))
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = p.stderr.readlines(timeout=0.5)))
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = traceback.format_exc()))
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = p.stdout.readlines(timeout=0.5)))
			#traceback.print_exc(file=sys.stderr)
			return None, [], []

		all_stdout = []
		all_stderr = []
		try:
			while p.commands[0].poll() is None:
				lines = p.stderr.readlines(timeout=0.5)
				if lines:
					lines = [self._to_unicode(x, errors="replace") for x in lines]
					#_log_stderr(*lines)
					all_stderr += list(lines)
					# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = all_stderr))
					# self.mgLog(lines,2)

				lines = p.stdout.readlines(timeout=0.5)
				if lines:
					lines = [self._to_unicode(x, errors="replace") for x in lines]
					#_log_stdout(*lines)
					all_stdout += list(lines)
					self._logger.info(lines)
					self._logger.info(all_stdout)
					# self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = all_stdout))
					# self.mgLog(lines,2)

		finally:
			p.close()

		lines = p.stderr.readlines()
		if lines:
			lines = [self._to_unicode(x, errors="replace") for x in lines]
			#_log_stderr(*lines)
			all_stderr += lines
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandError = all_stderr))
			self._logger.info(lines)
			# self.mgLog(lines,2)

		lines = p.stdout.readlines()
		if lines:
			lines = [self._to_unicode(x, errors="replace") for x in lines]
			#_log_stdout(*lines)
			all_stdout += lines

			self._logger.info(all_stdout)
			self._logger.info(all_stderr)
			# self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = all_stdout))
		return p.returncode, all_stdout, all_stderr


	def flashFirmware(self):
		if self.connectedPort == '':
			targetPort = "/dev/ttyUSB0"
		else:
			targetPort = self.connectedPort
		self.displayConnected = False
		self.tryToConnect = False
		self.nextionSerial.close()
		self.firmwareFlashingProgram = self._basefolder+"/static/supportfiles/nextion_uploader/nextion.py"

		self.firmwareLocation = self._basefolder+"/static/supportfiles/nextion_uploader/u1-v3-0124.tft"
		flashCommand = "/home/pi/oprint/bin/python " + self.firmwareFlashingProgram + " " + self.firmwareLocation + " " + targetPort
		if (self._execute(flashCommand)[0] == 0):
			self.tryToConnect = True
			self._logger.info("Firmware flashed!")
			self.connectionFails = 0


	def interval(self):
		if ((self.connectionFails + 1) * 5) > self.connectionMaxTimeBetween:
			return self.connectionMaxTimeBetween
		else:
			return ((self.connectionFails + 1) * 5)


	def nextionTimer(self):
		if self.displayConnected:
			# self._logger.info("nextionTimer triggered.")
			try:
				if self.nextionSerial.inWaiting() > 3:
					# self._logger.info("Enough bytes in inWaiting to do something.")
					# Do a bunch of stuff here, but primarily, check the shared list/array/whatever, if there's a set of three 0xFFs in a row or an endline or whatever, lock the array, remove that chunk for processing, unlock, and send that chunk for processing
					for i in range(0, self.nextionSerial.inWaiting()):
						inByte = self.nextionSerial.read()
						if inByte is None or inByte=="":
							return
						# self.receiveLog.append(inByte)
						self.receiveLog.append(inByte.decode("latin1"))
						# self._logger.info("receiveLog:")
						# self._logger.info(self.receiveLog)
			except Exception as e:
				self._logger.info("nextionTimer exception :"+str(sys.exc_info()[0]))
				self._logger.info(str(e))
				self.commFails += 1
				if self.commFails >=20:
					self.displayConnected = False


	def parseLog(self):
		# self._logger.info("parseLog triggered")
		if '\x00' in self.receiveLog:
			self.receiveLog.popleft()
		elif '\xff' in self.receiveLog:
			# self._logger.info("xff in receiveLog")
			try:
				ffCount = 0
				tempResponse = deque([])
				while ffCount < 3:
					# self._logger.info("popping first index")

					tempVal = self.receiveLog.popleft()
					if tempVal == '\xff':
						ffCount += 1
					tempResponse.append(tempVal)
					if not self.receiveLog:
						break
				self._logger.info(tempResponse)
				self.processMessage(tempResponse)

			except Exception as e:
				self._logger.info("xff parseLog exception: "+str(e))
				self._logger.info(tempResponse)
				traceback.print_exc()


		elif '\n' in self.receiveLog:
			# self._logger.info(" slashn in receiveLog")
			try:
				# self.logLock.acquire()
				tempLog = deque([])
				lastPos = list(self.receiveLog).index('\n')
				for i in range(0, lastPos+1):
					tempLog.append(self.receiveLog.popleft())
				# self._logger.info("tempLog:")
				# self._logger.info(tempLog)
				self.processMessage(tempLog)

			# finally:
			# 	self.logLock.release()
			except Exception as e:
				self._logger.info("n parseLog exception: "+str(e))
				self._logger.info(tempLog)
				traceback.print_exc()


	def populateIpAddress(self):
		if self.displayConnected:
			try:
				ip = str(([l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]))
			except socket.error as e:
				self._logger.info("Socket exception: "+str(e))
				ip = "No IP"
			self.nextionDisplay.nxWrite('home.ip.txt="{}"'.format(ip))


	def on_after_startup(self):
		self._logger.info("Mglcd plugin loaded!")
		self._printer.register_callback(self)
		self.displayConnectionTimer.start()


	def on_shutdown(self):
		self._logger.info("Shutting down - trying to display shutdown info on LCD.")
		try:
			self.nextionDisplay.nxWrite('page shuttingDown')
		except:
			return

	def connect_to_display(self):
		if self.tryToConnect:
			if not self.displayConnected:
				self.receiveLog.clear()
				self._logger.info("Trying to connect to display.")
				ports = self.serial_ports()
				self._logger.info("Ports found: ")
				self._logger.info(ports)
				# self.displayConnected = False
				# self.displayConnectionTimer.cancel()
				for port in ports:
					try:
						self._logger.info("Trying to get serial port.")

						self.nextionSerial = serial.Serial(port,115200,timeout=0.1)
						self.nextionSerial.flushInput()
						self.nextionSerial.flushOutput()
						# self.nextionSerial.write('bauds=115200'+chr(255)+chr(255)+chr(255))

						self._logger.info("Got serial, trying to initialize Nextion.")

						self.nextionDisplay = Nextion(self.nextionSerial)
						# self.nextionDisplay.nxWrite('bauds=115200')
						# self.nextionDisplay.nxWrite('Tool0.tempDisplay.txt="No Data Yet"')
						self.nextionDisplay.nxWrite('get home.handshake.txt')
						self.connectionFails += 1
						self.displayConnected = True
						try:
							self.serialReceiveTimer.start()
							self.serialParseTimer.start()
						except RuntimeError as e:
							self._logger.info("Exception!  Probably not happy about starting threads again?  Actual error: "+str(e))

					# except RuntimeError as e:
					except OSError as e:
						self._logger.info("OSError Exception!  Could not connect for some reason.")
						# self._logger.info("Error: "+str(e))
						self._logger.info("Error:"+str(e))
						self.displayConnected = False
						self.connectionFails += 1

					except Exception as e:
						self._logger.info("Exception!  Could not connect for some reason.")
						self._logger.info("Error: "+str(e))
						self._logger.info("Error:"+str(sys.exc_info()[0]))
						self.displayConnected = False
						self.connectionFails += 1
						# self.displayConnectionTimer.start()
					return self.displayConnected
				self.connectionFails += 1


	def handshakeReceived(self):

		self.nextionDisplay.nxWrite('page home')
		self.nextionDisplay.nxWrite('home.bedDisplay.txt="No Data"')
		self.nextionDisplay.nxWrite('home.tool0Display.txt="No Data"')
		self.nextionDisplay.nxWrite('home.tool1Display.txt="No Data"')
		# self.getMessage()
		self.nextionSerial.flushInput()
		self.nextionSerial.flushOutput()
		self.nextionDisplay.nxWrite('home.hostname.txt="{}"'.format(socket.gethostname()))
		self.nextionDisplay.nxWrite('home.name.txt="{}"'.format(str(octoprint.settings.Settings.get(octoprint.settings.settings(),["appearance", "name"])).strip('[\']')))
		# try:
		# 	ip = str(([l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]))
		# except socket.error as e:
		# 	self._logger.info("Socket exception: "+str(e))
		# 	ip = "No IP"
		# self.nextionDisplay.nxWrite('home.ip.txt="{}"'.format(ip))
		self.populateIpAddress()
		self.nextionDisplay.nxWrite('home.status.txt="Status: LCD Connected"')
		self._logger.info("LCD Firmware version:")
		self.nextionDisplay.nxWrite('get info.version.txt')
		# self.nextionDisplay.nxWrite('Status.t0.txt="LCD Connected"')

		self.displayConnected = True
		self.currentPage = 'home'
		# self.displayConnectionTimer.cancel()

		self.connectionFails = 0
		self._logger.info("Connected to display on port:")
		self._logger.info(self.nextionSerial.port)
		self.connectedPort = self.nextionSerial.port
		# self.nextionDisplay.nxWrite('touch_j')
		self.populateWifiList()
		self.ipTimer.start()


	def shortenFileName(self, longName):
		if len(longName) > 48:
			return (longName[:30]+'...'+longName[-10:])
		else:
			return longName


	def navigateFolderUp(self):
		try:
			tempPath = self.currentPath.split("/")
			tempPath.pop()
			self.currentPath = "/".join(tempPath)

		except Exception as e:
			self._logger.info("Error when trying to navigate up: "+str(e))


	def populatePrintList(self):
		self.files = self._file_manager.list_files(path=self.currentPath)
		self._logger.info(self.files)
		i = 0
		tempFileList = defaultdict(list)
		tempFolderList = defaultdict(list)
		navigateUpList = defaultdict(list)
		self.fileList = OrderedDict()
		if self.currentPath != '':
			self.fileList[0] = [
								{'name' : 'up' },
								{'path' : '' },
								{'shortName' : '..' },
								{'type' : 'folder' }
							]
			i = 1
		for file in sorted(list(self.files['local'].keys()), key = lambda x: x.lower()):
			if self.files['local'][file]['type'] == 'folder':
				self.fileList[i] = [
									{'name' : self.files['local'][file]['name'] },
									{'path' : self.files['local'][file]['path'] },
									{'shortName' : self.shortenFileName(self.files['local'][file]['name']) + "/" },
									{'type' : self.files['local'][file]['type'] }
									]
				i += 1

		for file in sorted(list(self.files['local'].keys()), key = lambda x: x.lower()):

			if self.files['local'][file]['type'] == 'machinecode':
				self.fileList[i] = [
									{'name' : self.files['local'][file]['name'] },
									{'path' : self.files['local'][file]['path'] },
									{'shortName' : self.shortenFileName(self.files['local'][file]['name']) },
									{'type' : self.files['local'][file]['type'] }
								]
				i += 1

		self._logger.info(self.fileList)

		self.showFileList()
		# Brakes the print menu
		#self.showDeleteFileList()

	def populateDeleteList(self):
		self.deleteFiles = self._file_manager.list_files(path=self.currentPath)
		self._logger.info(self.deleteFiles)
		i = 0
		self.deleteList = OrderedDict()
		if self.currentPath != '':
			self.deleteList[0] = [
								{'name' : 'up' },
								{'path' : '' },
								{'shortName' : '..' },
								{'type' : 'folder' }
							]
			i = 1
		for file in sorted(list(self.deleteFiles['local'].keys()), key = lambda x: x.lower()):
			if self.deleteFiles['local'][file]['type'] == 'folder':
				self.deleteList[i] = [
									{'name' : self.deleteFiles['local'][file]['name'] },
									{'path' : self.deleteFiles['local'][file]['path'] },
									{'shortName' : self.shortenFileName(self.deleteFiles['local'][file]['name']) + "/" },
									{'type' : self.deleteFiles['local'][file]['type'] }
									]
				i += 1

		for file in sorted(list(self.deleteFiles['local'].keys()), key = lambda x: x.lower()):

			if self.deleteFiles['local'][file]['type'] == 'machinecode':
				self.deleteList[i] = [
									{'name' : self.deleteFiles['local'][file]['name'] },
									{'path' : self.deleteFiles['local'][file]['path'] },
									{'shortName' : self.shortenFileName(self.deleteFiles['local'][file]['name']) },
									{'type' : self.deleteFiles['local'][file]['type'] }
								]
				i += 1

		self._logger.info(self.deleteList)
		self.showDeleteFileList()

	def populateWifiList(self):
		tempWifiList = self._send_message("list_wifi",{})
		self.wifiList = defaultdict(list)
		i = 0
		for ssid in tempWifiList[1]:
			self.wifiList[i] = tempWifiList[1][i]["ssid"]
			i += 1


		self._logger.info(self.wifiList)
		self.showWifiList()


	def showWifiList(self):
		j = self.wifiListLocation
		i = 0
		self._logger.info(str(len(self.wifiList))+" long; location: "+str(self.wifiListLocation))

		for clearPos in range (0,5):
			self.nextionDisplay.nxWrite('wifilist.wifi{}.txt="{}"'.format(clearPos,('')))
		lastPos = 5
		if (len(self.wifiList)-j)<5:
			lastPos = (len(self.wifiList) - j)
		for wifiCount in range(0,lastPos):
			try:
				wifiString = 'wifilist.wifi{}.txt="{}"'.format(i,(self.wifiList[wifiCount+j]))
				self._logger.info("wifiCount: "+str(wifiCount)+" ; wifiString: "+wifiString)
				self.nextionDisplay.nxWrite(wifiString)
				i += 1

			except KeyError as e:
				self._logger.info("Encountered key error: " + str(e))
				break

			except Exception as e:
				self._logger.info("More general exception in showWifiList: "+str(e))
				break


	def showFileList(self):
		j = self.fileListLocation
		i = 0

		for clearPos in range (0,5):
			self.nextionDisplay.nxWrite('files.file{}.txt="{}"'.format(clearPos,('')))
		lastPos = 5
		for fileCount in range(0,lastPos):
			try:
				fileNameString = 'files.file{}.txt="{}"'.format(i,(self.fileList[fileCount+j][2]['shortName']))
				self.nextionDisplay.nxWrite(fileNameString)
				i += 1

			except KeyError as e:
				self._logger.info("Encountered key error: " + str(e))
				break

			except Exception as e:
				self._logger.info("More general exception in showFileList: "+str(e))
				break

	def showDeleteFileList(self):
		j = self.deleteListLocation
		i = 0

		for clearPos in range (0,5):
			self.nextionDisplay.nxWrite('deleteFiles.file{}.txt="{}"'.format(clearPos,('')))
		lastPos = 5
		for fileCount in range(0,lastPos):
			try:
				fileNameString = 'deleteFiles.file{}.txt="{}"'.format(i,(self.deleteList[fileCount+j][2]['shortName']))
				self.nextionDisplay.nxWrite(fileNameString)
				i += 1

			except KeyError as e:
				self._logger.info("Encountered key error: " + str(e))
				break

			except Exception as e:
				self._logger.info("More general exception in showDeleteFileList: "+str(e))
				break

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self.address = self._settings.get(["socket"])


	def get_settings_defaults(self):
		return dict(
			socket="/var/run/netconnectd.sock",
			hostname=None,
			timeout=10
		)


	def get_template_configs(self):
		return [
			dict(type="settings", name="Network connection")
		]


	def get_api_commands(self):
		return dict(
			start_ap=[],
			stop_ap=[],
			refresh_wifi=[],
			configure_wifi=[],
			forget_wifi=[],
			reset=[]
		)
	

	def is_api_adminonly(self):
		return True


	def on_api_get(self, request):
		try:
			status = self._get_status()
			if status["wifi"]["present"]:
				wifis = self._get_wifi_list()
			else:
				wifis = []
		except Exception as e:
			return jsonify(dict(error=str(e)))

		return jsonify(dict(
			wifis=wifis,
			status=status,
			hostname=self.hostname
		))


	def on_api_command(self, command, data):
		if command == "refresh_wifi":
			return jsonify(self._get_wifi_list(force=True))

		# any commands processed after this check require admin permissions
		if not admin_permission.can():
			return make_response("Insufficient rights", 403)

		if command == "configure_wifi":
			if data["psk"]:
				self._logger.info("Configuring wifi {ssid} and psk...".format(**data))
			else:
				self._logger.info("Configuring wifi {ssid}...".format(**data))

			self._configure_and_select_wifi(data["ssid"], data["psk"], force=data["force"] if "force" in data else False)

		elif command == "forget_wifi":
			self._forget_wifi()

		elif command == "reset":
			self._reset()

		elif command == "start_ap":
			self._start_ap()

		elif command == "stop_ap":
			self._stop_ap()


	##~~ AssetPlugin mixin
	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/mglcd.js"],
			css=["css/mglcd.css"],
			less=["less/mglcd.less"]
		)

	def get_api_commands(self):
		return dict(flashNextionFirmware=[])

	def on_api_command(self, command, data):
		if command == 'flashNextionFirmware':
			self.flashFirmware()

	def get_template_configs(self):
		return [dict(type="settings", template="octoprint_mglcd_settings.jinja2", div="mglcdSettings", custom_bindings=True)]


	##~~ Softwareupdate hook
	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			mglcd=dict(
				displayName="MakerGear LCD",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="MakerGear",
				repo="OctoPrint-Mglcd-U1",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/MakerGear/OctoPrint-Mglcd-U1/archive/{target_version}.zip"
			)
		)


	def on_printer_send_current_data(self,data):
		if self.displayConnected:
			tempData = self._printer.get_current_temperatures()

			if self.currentPage == 'home' or self.currentPage == 'temperature' or self.currentPage == 'extruder':
				try:
					displayString = self.currentPage + '.tool0Display.txt="{} / {} \xB0C"'.format(str(int(tempData['tool0']['actual'])),str(int(tempData['tool0']['target'])))
					displayGeneralString = 'tool0.tool0Display.txt="{} / {} \xB0C"'.format(str(int(tempData['tool0']['actual'])),str(int(tempData['tool0']['target'])))

					self.nextionDisplay.nxWrite(displayString)
					self.nextionDisplay.nxWrite(displayGeneralString)
				except:
					self._logger.info('no tool0?')
					tool0DisplayString = self.currentPage + '.tool0Display.txt="No Data"'
					tool0GeneralDisplayString = 'tool0.tool0Display.txt="No Data"'
					self.nextionDisplay.nxWrite(tool0DisplayString)
					self.nextionDisplay.nxWrite(tool0GeneralDisplayString)

				try:
					tool1DisplayString = self.currentPage + '.tool1Display.txt="{} / {} \xB0C"'.format(str(int(tempData['tool1']['actual'])),str(int(tempData['tool1']['target'])))
					tool1DisplayGeneralString = 'tool1.tool1Display.txt="{} / {} \xB0C"'.format(str(int(tempData['tool1']['actual'])),str(int(tempData['tool1']['target'])))

					self.nextionDisplay.nxWrite(tool1DisplayString)
					self.nextionDisplay.nxWrite(tool1DisplayGeneralString)
				except:
					self._logger.info('no tool1?')
					tool1DisplayString = self.currentPage + '.tool1Display.txt="No Tool1"'
					tool1GeneralDisplayString = 'tool1.tool1Display.txt="No Tool1"'

					self.nextionDisplay.nxWrite(tool1DisplayString)
					self.nextionDisplay.nxWrite(tool1GeneralDisplayString)

			if self.currentPage == 'printcontrols':
				if self._printer.get_state_id() == "PAUSED":
					# If OctoPrint is paused, display "Resume" on the LCD
					# If the display already says "Resume", don't change it
					if self.nextionDisplay.nxRead('printcontrols.toggle.txt') != "Resume":
						self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Resume"')
				else:
					# OctoPrint is not paused
					# If the display already says "Pause", don't change it
					if self.nextionDisplay.nxRead('printcontrols.toggle.txt') != "Pause":
						self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Pause"')

				if (data['job']['file']['name']) == None:
					filePrintingString = self.currentPage + '.fileName.txt="No File"'
				else:
					filePrintingString = self.currentPage + '.fileName.txt="{}"'.format(data['job']['file']['name'])

				if data['job']['estimatedPrintTime'] is not None:
					tempTime = int(data['job']['estimatedPrintTime']/60)
					if tempTime > 60:
						tempTimeString = str(int(math.floor(tempTime/60)))+" hrs " + str(int(math.fmod(tempTime,60))) + " min"
					else:
						tempTimeString = str(tempTime) + " min"
					fileTimeLeftString = self.currentPage + '.fileTime.txt="Print Time: {}"'.format(tempTimeString)
				#except Exception as e:
				else:
					fileTimeLeftString = self.currentPage + '.fileTime.txt="Print Time: No Data"'
					self._logger.info("Exception when populating file print time:")

				try:
					self.filamentInFile = 0.0
					for tool in list(data['job']['filament'].keys()):
						self.filamentInFile = self.filamentInFile + data['job']['filament'][tool]['length']
					fileUsedFilamentString = self.currentPage + '.filament.txt="Filament: {} m"'.format(str(round((self.filamentInFile/1000),2)))
				except Exception as e:
					fileUsedFilamentString = self.currentPage + '.filament.txt="Filament: No Data"'

				self.nextionDisplay.nxWrite(filePrintingString)
				self.nextionDisplay.nxWrite(fileTimeLeftString)
				self.nextionDisplay.nxWrite(fileUsedFilamentString)

			if self.currentPage == 'home' or self.currentPage == 'temperature':
				bedDisplayString = self.currentPage + '.bedDisplay.txt="{} / {} \xB0C"'.format(str(int(tempData['bed']['actual'])),str(int(tempData['bed']['target'])))

				self.nextionDisplay.nxWrite(bedDisplayString)

			if self.currentPage == 'home':
				if (data['job']['file']['name']) == None:
					filePrintingString = self.currentPage + '.filePrinting.txt="No File Selected"'
				else:
					filePrintingString = self.currentPage + '.filePrinting.txt="{}"'.format(data['job']['file']['name'])

				try:
					fileProgressString = self.currentPage + '.fileProgress.val={}'.format(str(int(data['progress']['completion'])))
				except:
					fileProgressString = self.currentPage + '.fileProgress.val=0'

				try:
					fileProgressPercentString = self.currentPage + '.filePercent.txt="{}%"'.format(str(int(data['progress']['completion'])))
				except:
					fileProgressPercentString = self.currentPage + '.filePercent.txt="0%"'

				try:
					tempTime = int(data['progress']['printTimeLeft']/60)
					if tempTime > 60:
						tempTimeString = str(int(math.floor(tempTime/60)))+" hrs " + str(int(math.fmod(tempTime,60))) + " min"
					else:
						tempTimeString = str(tempTime) + " min"
					fileTimeLeftString = self.currentPage + '.fileTimeLeft.txt="Est.: {}"'.format(tempTimeString)
				except:
					fileTimeLeftString = self.currentPage + '.fileTimeLeft.txt="Est.: 0 min"'

				try:
					stateString = self.currentPage + '.status.txt="Status: {}"'.format(data['state']['text'])
				except:
					stateString = self.currentPage + '.status.txt="Status: Connected"'

				self.nextionDisplay.nxWrite(filePrintingString)
				self.nextionDisplay.nxWrite(fileProgressString)
				self.nextionDisplay.nxWrite(fileTimeLeftString)
				self.nextionDisplay.nxWrite(fileProgressPercentString)
				self.nextionDisplay.nxWrite(stateString)


	def showMessage(self,message):
		#this is a general function to switch to the messages page on the LCD and update the two text boxes.
		self.nextionDisplay.nxWrite('messages.text0.txt="Message pending."')
		self.nextionDisplay.nxWrite('messages.text1.txt=""')
		self.nextionDisplay.nxWrite('page messages')
		if len(message)>254:
			self.nextionDisplay.nxWrite('messages.text0.txt="{}"'.format(message[0:253]))
			if len(message)>508:
				self.nextionDisplay.nxWrite('messages.text1.txt="{}"'.format(message[253:506]))
		else:
			self.nextionDisplay.nxWrite('messages.text0.txt="{}"'.format(message))


	def getMessage(self):
		if self.displayConnected:
			# if self.nextionSerial.inWaiting() > 1:
			try:
				line = self.nextionSerial.readline()
				# line = self.nextionDisplay.nxRead()
				self.processMessage(line)
			except:
				self._logger.info("Exception!  readline() failed.")
				self._logger.info("Error:"+str(sys.exc_info()[0]))

			# tt = threading.Timer(.125, self.getMessage, {})
			# tt.start()

	def processMessage(self, lineRaw):
		line = ''.join(lineRaw)
		line = line.rstrip()

		if "MAKERGEAR" in str(line):
			self._logger.info("Handshake received.")
			self.handshakeReceived()

		if "page " in str(line):
			self.currentPage = line.split(' ')[1]
			if self.currentPage == 'splash':
				self.handshakeReceived()
			if self.currentPage == 'home':
				self.fileListLocation = 0
				self.deleteListLocation = 0
			if self.currentPage == 'wifipassword':
				self.nextionDisplay.nxWrite('wifipassword.header.txt="Connecting to : {}"'.format(self.chosenSsid))

		if "set" in str(line):
			if "tool0:" in str(line):
				m = re.search('(?<=:)\d+', str(line))
				self._logger.info(m.group(0))
				self._printer.set_temperature("tool0",int(m.group(0)))

			if "tool1:" in str(line):
				m = re.search('(?<=:)\d+', str(line))
				self._logger.info(m.group(0))
				self._printer.set_temperature("tool1",int(m.group(0)))

			if "bed:" in str(line):
					m = re.search('(?<=:)\d+', str(line))
					self._logger.info(m.group(0))
					if not self.rrf:
						self._printer.set_temperature("bed",int(m.group(0)))
					else:
						self._printer.commands(["M140 P0 S"+str(int(m.group(0))),
							"M140 P1 S"+str(int(m.group(0))+2),
							"M140 P2 S"+str(int(m.group(0))+4),
							"M140 P3 S"+str(int(m.group(0))+4)])

		if "button" in line:
			splitLine = line.split(" ")
			if splitLine[1] in ("x0", "x1", "y", "z", "t0", "t1"):
				axis = list(splitLine[1])[0]
				try:
					distance = float(splitLine[3])
				except IndexError:
					distance = 0

				if splitLine[2] == "negative":
					direction = -1
				elif splitLine[2] == "positive":
					direction = 1
				elif splitLine[2] == "babystep":
					self._printer.commands("M290 Z"+str(distance))

				if splitLine[1] in ("x0", "t0"):
					self._printer.change_tool("tool0")
				elif splitLine[1] in ("x1", "t1"):
					self._printer.change_tool("tool1")

				if splitLine[1] in ("t0", "t1"):
					self._printer.extrude(int(splitLine[2]))
					return

				if axis == "x":
					speed = 2000
				elif axis == "y":
					speed = 1500
				elif axis == "z":
					speed = 500

				moveDict = {}
				moveDict[axis] = (distance * direction)
				self._printer.jog(moveDict, speed = speed)

			if line == "button fileMenu page":
				self.fileListLocation = 0
				self.currentPage = 'fileList'
				self.currentFolder = ''
				self.populatePrintList()
				return
			
			if line == "button deleteMenu page":
				self.deleteListLocation = 0
				self.currentPage = 'deleteList'
				self.currentFolder = ''
				self.populateDeleteList()
				return

			if line == "button wifilist page":
				self.wifiListLocation = 0
				self.currentPage = 'wifilist'
				self.populateWifiList()
				return

			if line == "button wifi refresh":
				self.wifiListLocation = 0
				self.currentPage = 'wifilist'
				self.populateWifiList()
				return

			if line == "button ap start":
				self._reset()
				self._execute("/home/pi/.octoprint/scripts/resetRpi.sh")

			if line == "button ap stop":
				self.nextionDisplay.nxWrite('page messages')
				tempResponse = self._stop_ap()
				self.showMessage(tempResponse)

			if line == "button network info":
				currentStatus = self._get_status()
				self.showMessage(currentStatus)

			if "button password" in line:
				password = line[16:]
				self._logger.info(password)
				connectResponse = "Connection failed."
				try:
					connectResponse = self._configure_and_select_wifi(self.chosenSsid, password)
				except Exception as e:
					self._logger.info("Error while trying to connect to wifi: "+str(e))
					connectResponse = "Error while trying to connect to wifi: "+str(e)

			if "button wifi" in line:
				self._logger.info(line)
				pattern = ' [^\s]*$'
				try:
					wifiButton = (re.search(pattern, line)).group(0).strip()
					if wifiButton.isdigit():
						try:
							self.chosenSsid = str(self.wifiList[int(wifiButton)+self.wifiListLocation])
						except Exception as e:
							self._logger.info(str(e))

					if wifiButton == "left":
						if self.wifiListLocation >= 2:
							self.wifiListLocation -= 2
						else:
							self.wifiListLocation = 0
						self.showWifiList()

					if wifiButton == "right":
						if self.wifiListLocation < len(self.wifiList) - 4:
							self.wifiListLocation += 2
						else:
							self.wifiListLocation = len(self.wifiList) - 3
						self.showWifiList()
				except Exception as e:
					self._logger.info(str(e))

			if "button fileMenu" in line:
				self._logger.info(line)
				pattern = ' [^\s]*$'
				try:
					fileButton = (re.search(pattern, line)).group(0).strip()

					if fileButton.isdigit():
						self._logger.info(self.previousFolderList)
						try:
							if self.fileList[int(fileButton)+self.fileListLocation][3]['type'] == 'folder':
								if self.fileList[int(fileButton)+self.fileListLocation][0]['name'] == 'up':
									self.navigateFolderUp()
									self.populatePrintList()

								else:
									self.currentFolder = self.fileList[int(fileButton)+self.fileListLocation][1]['path']
									self.currentPath = self.fileList[int(fileButton)+self.fileListLocation][1]['path']
									self.fileListLocation = 0
									self.populatePrintList()
							else:
								self._printer.select_file((self._file_manager.sanitize_path('local',(self.fileList[int(fileButton)+self.fileListLocation][1]['path']))), False)
								self.nextionDisplay.nxWrite('page printcontrols')
								self._logger.info(line)

						except KeyError as e:
							self._logger.info("Keyerror when selecting file: "+str(e))
							traceback.print_exc()
							self._logger.info(line)

						except Exception as e:
							self._logger.info("General exception when selecting file: "+str(e))
							traceback.print_exc()
							self._logger.info(line)

					if fileButton == "left":
						if self.fileListLocation >= 2:
							self.fileListLocation -= 2
						else:
							self.fileListLocation = 0
						self.showFileList()
					if fileButton == "right":
						if self.fileListLocation < len(self.fileList) - 4:
							self.fileListLocation += 2
						else:
							self.fileListLocation = len(self.fileList) - 3
						self.showFileList()
				
				except Exception as e:
					self._logger.info(str(e))

			if line == "button home all":
				if not self.rrf:
					self._printer.home(("x","y","z"))
				else:
					self._printer.commands(["G28 XY",
						"G28 Z"])

			if line == "button home x":
				self._printer.home(("x"))

			if line == "button home y":
				self._printer.home(("y"))

			if line == "button home z":
				self._printer.home(("z"))

			if line == "button print start":
				# select and start printing the selected file
				# pass
				self._printer.start_print()
				self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Pause"')
				self.currentPage = 'home'

			if line == "button print cancel":
				# select and start printing the selected file
				# pass
				self._printer.cancel_print()
				self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Pause"')
				# self.currentPage = 'home'

			if line == "button print toggle":
				# select and start printing the selected file
				# pass
				# self._printer.toggle_pause_print()
				# self.currentPage = 'home'

				# TODO code in here to go to either pauseConfirm or resumeConfirm depending on current print state; also toggle the labels
				if self._printer.is_printing():
					self.nextionDisplay.nxWrite("page pauseConfirm")
				elif self._printer.is_paused():
					self.nextionDisplay.nxWrite("page resumeConfirm")

			if line == "button print pause":
				# select and start printing the selected file
				# pass
				self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Resume"')
				self._printer.pause_print()
				# self.currentPage = 'home'

			if line == "button print resume":
				# select and start printing the selected file
				# pass
				self.nextionDisplay.nxWrite('printcontrols.toggle.txt="Pause"')
				self._printer.resume_print()
				# self.currentPage = 'home'

			if line == "button printer reset":
				self._execute("/home/pi/.octoprint/scripts/resetRambo.sh")
				# pass
			if line == "button octoprint restart":
				self._execute("/home/pi/.octoprint/scripts/resetOctoprint.sh")
				# pass
			if line == "button pi shutdown":
				self._execute("/home/pi/.octoprint/scripts/shutdownRpi.sh")
				# pass
			if line == "button pi reboot":
				self._execute("/home/pi/.octoprint/scripts/resetRpi.sh")
				# pass

			if line == "button lcd disconnect":
				self.nextionDisplay.nxWrite('page notConnected')
				self.tryToConnect = False
				self.nextionSerial.flushInput()
				self.nextionSerial.flushOutput()
				self.nextionSerial.close()
				self.displayConnected = False
				self._logger.info("LCD disconnected!")

			if line == "button general motors off":
				self._printer.commands("M84")

			if line == "button fan on":
				self._printer.commands("M106 P0 S255")
				self._printer.commands("M106 P3 S255")

			if line == "button fan off":
				self._printer.commands("M106 P0 S0")
				self._printer.commands("M106 P3 S0")

			if line == "button QR Code":
				self.setQR()

			# Cold Extrude Menu new code 5-23-34 by Garrett
			if line == "button cold extrude":
				self._printer.commands("M302 P1")

			# Homing Option Menu new code 5-23-34 by Garrett
			if line == "button homing disabled":
				self._printer.commands("M564 S0 H0")
			
			if line == "button collect logs": 
				self.collectLogs()

			if "button deleteMenu" in line:
				self._logger.info(line)
				pattern = ' [^\s]*$'
				try:
					fileButton = (re.search(pattern, line)).group(0).strip()
					if fileButton.isdigit():
						self._logger.info(self.previousFolderList)
						try:
							if self.deleteList[int(fileButton)+self.deleteListLocation][3]['type'] == 'folder':
								if self.deleteList[int(fileButton)+self.deleteListLocation][0]['name'] == 'up':
									self.navigateFolderUp()
									self.populateDeleteList()

								else:
									self.currentFolder = self.deleteList[int(fileButton)+self.deleteListLocation][1]['path']
									self.currentPath = self.deleteList[int(fileButton)+self.deleteListLocation][1]['path']
									self.deleteListLocation = 0
									self.populateDeleteList()

							else:
								# works for now, but need to add a confirmation dialog
								self._file_manager.remove_file('local', self.deleteList[int(fileButton)+self.deleteListLocation][1]['path'])
								self.populateDeleteList()
								#self._logger.info("deleted: " + self.deleteList[int(fileButton)+self.deleteListLocation][1]['path'])
								#self._logger.info(line)

						except KeyError as e:
							self._logger.info("Keyerror when selecting file: "+str(e))
							traceback.print_exc()
							self._logger.info(line)

						except Exception as e:
							self._logger.info("General exception when selecting file: "+str(e))
							traceback.print_exc()
							self._logger.info(line)

					if fileButton == "left":
						if self.deleteListLocation >= 2:
							self.deleteListLocation -= 2
						else:
							self.deleteListLocation = 0
						self.showDeleteFileList()
					if fileButton == "right":
						if self.deleteListLocation < len(self.deleteList) - 4:
							self.deleteListLocation += 2
						else:
							self.deleteListLocation = len(self.deleteList) - 3
						self.showDeleteFileList()
				
				except Exception as e:
					self._logger.info(str(e))


	def _get_wifi_list(self, force=False):
		payload = dict()
		if force:
			self._logger.info("Forcing wifi refresh...")
			payload["force"] = True

		flag, content = self._send_message("list_wifi", payload)
		if not flag:
			raise RuntimeError("Error while listing wifi: " + content)

		result = []
		for wifi in content:
			result.append(dict(ssid=wifi["ssid"], address=wifi["address"], quality=wifi["signal"], encrypted=wifi["encrypted"]))
		return result

	def _get_status(self):
		payload = dict()

		flag, content = self._send_message("status", payload)
		if not flag:
			raise RuntimeError("Error while querying status: " + content)

		return content

	def _configure_and_select_wifi(self, ssid, psk, force=False):
		payload = dict(
			ssid=ssid,
			psk=psk,
			force=force
		)

		flag, content = self._send_message("config_wifi", payload)
		if not flag:
			raise RuntimeError("Error while configuring wifi: " + content)

		flag, content = self._send_message("start_wifi", dict())
		if not flag:
			raise RuntimeError("Error while selecting wifi: " + content)
		return content
		
	def _forget_wifi(self):
		payload = dict()
		flag, content = self._send_message("forget_wifi", payload)
		if not flag:
			raise RuntimeError("Error while forgetting wifi: " + content)
		return content

	def _reset(self):
		payload = dict()
		flag, content = self._send_message("reset", payload)
		if not flag:
			raise RuntimeError("Error while factory resetting netconnectd: " + content)

	def _start_ap(self):
		payload = dict()
		flag, content = self._send_message("start_ap", payload)
		if not flag:
			raise RuntimeError("Error while starting ap: " + content)

	def _stop_ap(self):
		payload = dict()
		flag, content = self._send_message("stop_ap", payload)
		if not flag:
			raise RuntimeError("Error while stopping ap: " + content)
		return content

	def _send_message(self, message, data):
		obj = dict()
		obj[message] = data

		import json
		js = json.dumps(obj, separators=(",", ":")).encode("utf8")

		import socket
		sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		sock.settimeout(self._settings.get_int(["timeout"]))
		try:
			sock.connect(self.address)
			sock.sendall(js + b'\x00')

			buffer = []
			while True:
				chunk = sock.recv(16)
				if chunk:
					buffer.append(chunk)
					if chunk.endswith(b'\x00'):
						break

			data = b''.join(buffer).strip()[:-1]

			response = json.loads(data.strip())
			if "result" in response:
				return True, response["result"]

			elif "error" in response:
				# something went wrong
				self._logger.warning("Request to netconnectd went wrong: " + response["error"])
				return False, response["error"]

			else:
				output = "Unknown response from netconnectd: {response!r}".format(response=response)
				self._logger.warning(output)
				return False, output

		except Exception as e:
			output = "Error while talking to netconnectd: {}".format(e)
			self._logger.warning(output)
			return False, output

		finally:
			sock.close()


	def setQR(self):
		self._logger.info("Setting QR code.")
		qrText = "http://" + self.hostname + "/"

		# Write qrText to display via txt
		self.nextionDisplay.nxWrite('qrMenu.qr0.txt="' + qrText + '"')


	def copyFiles(self, src_dir, dst_dir):
		for dirpath, dirnames, filenames in os.walk(src_dir):
			for filename in filenames:
				src_file = os.path.join(dirpath, filename)
				shutil.copy(src_file, dst_dir)


	def collectLogs(self):
		# Change the display to the downloading page
		self.nextionDisplay.nxWrite('page downloading')

		# Determine if any USB drive is mounted
		mountedDrive = None

		# Python version check
		# if sys.version_info[0] > 3:
		# 	# Python 3.6+ only for f strings
		usbPath = f"/media/usb{i}"
		# Python 2
		# usbPath = "/media/usb{}".format(i)

		for i in range(4):
			if os.path.exists(usbPath):
				self._logger.info("USB drive mounted at {}".format(usbPath))
				mountedDrive = usbPath
				break

		# If no USB drive is mounted, report an error and return to the home page
		if not mountedDrive:
			self._logger.info("No USB drive mounted, cannot collect logs.")
			self.nextionDisplay.nxWrite('downloading.t1.txt="Error: No USB drive found."')
			return

		# Create a zip file of the logs
		mainLogFolder = "/home/pi/.octoprint/logs"
		mainLogs =  os.listdir(mainLogFolder)

		# Grab the makergear logs from a different python site-packages folder
		# print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')
		mgLogFolder = "/home/pi/oprint/lib/python2.7/site-packages/octoprint_mgsetup/logs"
		
		# move the logs to the main log folder
		self.copyFiles(mgLogFolder, mainLogFolder)
		
		try:
			self._logger.info("Preparing Logs, Please Wait.")
			zipNameDate = "MGSetup-Logs-" + "-" + str(datetime.datetime.now().strftime('%y-%m-%d_%H-%M'))
			zipname = self._basefolder+"/static/supportfiles/logs/" + zipNameDate +".zip"
			with ZipFile(zipname, 'w', ZIP_DEFLATED) as logzip:
				for file_name in mainLogs:
					tempfile = os.path.join(mainLogFolder, file_name)
					logzip.write(tempfile, os.path.basename(tempfile))

			self._logger.info("Downloading File: "+str(zipNameDate)+".zip")
			# move the zip file to the usb drive
			self._logger.info("Moving zip file to USB drive.")
			shutil.move(zipname, usbPath)
			
		except Exception as e:
			self._logger.info("collectLogs failed, exception: " + str(e))
		
		# return to the home page
		self.nextionDisplay.nxWrite("page home")

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Mglcd Plugin"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = NextionPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
