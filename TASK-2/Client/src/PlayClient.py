from tkinter import *
import tkinter.messagebox as MessageBox
from PIL import Image, ImageTk
from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
import socket, threading, sys, traceback, os
import random
import time
from math import *

from RtpPacket import RtpPacket
from Constants import Constants


class PlayClient:
	'''
	用于播放视频的客户端
	'''
	
	#初始化系列函数
	def __init__(self, master, TheServerIP, TheServerPort, TheFileName):
		'''
        描述：初始化RTP客户端
        参数：父控件，服务器的IP和端口，文件名
        返回：无
		'''
		#图形界面相关
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.QuitByHandler)

		#网络相关，包括服务器IP，端口信息，和自己的数据连接端口信息，还有数据，控制连接本身
		self.ClientIP = ""
		self.ServerIP = TheServerIP
		self.ServerPort = int(TheServerPort)
		self.DataPort = self.GenerateRandomPort()
		self.ControlSocket = None
		self.DataSocket = None

		#控制相关，包括Session，状态等
		self.Session = Constants.UNDEFINED_NUMBER
		self.RequestSent = ""
		self.Valid = True
		self.Status = Constants.RTP_TRANSPORT_INIT

		#控制，数据连接顺序码和数据连接的帧
		self.ControlSequence = 0
		self.DataSequence = 0
		self.PictureFrame = 0
		self.PicturePlay = 0

		#视频信息--总帧数，缓冲区时间，帧率
		self.PicturePerSecond = Constants.UNDEFINED_NUMBER
		self.TotalFrameNumber = Constants.UNDEFINED_NUMBER
		self.BufferTime = 10

		#文件相关，包括要播放的视频文件名，缓存文件和接收文件的文件格式和目录名
		self.FileName = TheFileName
		self.CacheDirPicture = "CachePicture"
		self.CacheFront = "Cache_"
		self.PictureBack = ".jpg"

		#进度条信息
		self.ScalerValueMax = Constants.UNDEFINED_NUMBER

		#播放速率
		self.CurrentPlaySpeed = 1

		#初始化操作：初始化控件，初始化目录，连接服务器,开始播放
		self.CreateWidgets()
		self.InitDir()
		self.ConnectToServer()
		self.SetupMovie()
		
	def InitDir(self):
		'''
		描述：初始化缓存目录
		参数：无
		返回：无
        '''		
		if os.path.exists(self.CacheDirPicture) == False:
			os.mkdir(self.CacheDirPicture)
		return

	def CreateWidgets(self):
		'''
		描述：初始化RTP客户端
        参数：无
        返回：无
		'''
		#暂停/继续按钮		
		self.Pause = Button(self.master, width = 20, padx = 3, pady = 3)
		self.Pause["text"] = "Pause"
		self.Pause["command"] = self.PauseMovie
		self.Pause.grid(row = 3, column = 0, padx = 2, pady = 2)
		
		#Teardown按钮
		self.Teardown = Button(self.master, width = 20, padx = 3, pady = 3)
		self.Teardown["text"] = "Teardown"
		self.Teardown["command"] =  self.ExitClient
		self.Teardown.grid(row = 3, column = 1, padx = 2, pady = 2)
		
		#图片显示
		self.Movie = Label(self.master)
		self.Movie.grid(row = 0, column = 0, columnspan = 4, sticky = W + E + N + S, padx = 5, pady = 5) 

		#播放速率选择
		self.CreateChoiceButtons()
	
	def CreateChoiceButtons(self):
		'''
		描述：初始化播放速率选择控件
        参数：无
        返回：无
		'''
		self.IntVarChoiceValue = IntVar()
		#播放速率列表
		self.PlaySpeedList = [(0.5, 0), (0.75, 1), (1, 2), (1.25, 3), (1.5, 4), (2, 5)]
		self.ChoiceShow = Label(self.master, text='选择播放速率')
		self.ChoiceShow.grid(row = 2, column = 2, padx = 2, pady = 2)
 
		#for循环创建单选框
		self.ChoiceButtonList = []
		for Speed, Num in self.PlaySpeedList:
			TheRadioButton = Radiobutton(self.master, text = "X" + str(Speed), value = Num, command = self.ChangePlaySpeed\
			, variable = self.IntVarChoiceValue)
			TheRadioButton.grid(row = 3 + Num, column = 2, padx = 1, pady = 0)
			self.ChoiceButtonList.append(TheRadioButton)
		#设置初始值
		self.IntVarChoiceValue.set(2)


	def CreateScaler(self):
		'''
		描述：初始化播放进度条和时间显示
        参数：无
        返回：无
		'''
		#播放进度条
		self.ScalerValueMax = round(self.TotalFrameNumber / self.PicturePerSecond)
		TheLabel = "0:00:00/" + self.GetPlayTime(self.TotalFrameNumber)

		#进度条时间
		self.ProgressShow = Label(self.master, width = 20)
		self.ProgressShow.grid(row = 1, column = 1, padx = 2, pady = 2)
		self.ProgressShow.configure(text = TheLabel)

		#进度条本身
		self.Scaler = Scale(self.master, label = '', from_ = 0, to = self.ScalerValueMax, orient = HORIZONTAL,
             length = 800, showvalue = 0, resolution = 1, command = self.ChangeScaler)
		self.Scaler.grid(row = 2, column = 0, padx = 2, pady = 2)

	#网络连接相关操作，包括数据端口连接服务器，控制端口开启等
	def ConnectToServer(self):
		'''
		描述：让RTSP控制连接服务器
		参数：无
		返回：无
        '''	
		self.ControlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.ControlSocket.connect((self.ServerIP, self.ServerPort))
		except:
			MessageBox.showwarning('Connection Failed', 'Connection to the server at \'%s\' failed.' %self.ServerIP)
	
	def OpenDataPort(self):
		'''
		描述：开启RTP数据端口，接收服务器数据
		参数：无
		返回：无
        '''	
		self.DataSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.DataSocket.settimeout(0.5)	
		try:
			self.DataSocket.bind(("", self.DataPort))
		except:
			MessageBox.showwarning('Unable to Bind', 'Unable to bind the data link at PORT = %d' %self.DataPort)

	#绑定按钮和事件处理相关操作，包括SETUP，PLAY，PAUSE，RESUME，TEARDOWN, GETPARAMETER，修改进度条，修改倍速，全屏
	def SetupMovie(self):
		'''
		描述：Setup操作
        参数：无
        返回：无
		'''		
		if self.Status == Constants.RTP_TRANSPORT_INIT:
			self.SendControlRequest("SETUP")
	
	def ExitClient(self):
		'''
		描述：Teardown操作，退出和删除缓存文件
        参数：无
        返回：无
		'''	
		self.SendControlRequest("TEARDOWN")		
		self.master.destroy() 
		try:
			#os.chdir(self.CacheDirPicture)
			for i in range(self.PictureFrame):
				TheCacheName = self.GetPictureCacheFileName(i + 1)
				os.remove(TheCacheName) 
			for i in range(self.AudioFrame):
				TheCacheName = self.GetAudioCacheFileName(i + 1)
				os.remove(TheCacheName) 
		except:
			donothing = True

	def QuitByHandler(self):
		'''
		描述：Teardown操作，不过用于绑定其他方式退出，而非按钮退出
        参数：无
        返回：无
		'''	
		self.PauseMovie()
		if MessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.ExitClient()
		else: # When the user presses cancel, resume playing.
			self.PlayMovie()

	def PauseMovie(self):
		'''
		描述：Pause操作
        参数：无
        返回：无
		'''	
		if self.Status == Constants.RTP_TRANSPORT_PLAYING:
			self.SendControlRequest("PAUSE")
	
	def ResumeMovie(self):
		'''
		描述：Resume操作
        参数：无
        返回：无
		'''	
		if self.Status == Constants.RTP_TRANSPORT_READY:
			self.SendControlRequest("RESUME")
	
	def PlayMovie(self):
		'''
		描述：Play操作
        参数：无
        返回：无
		'''	
		if self.Status == Constants.RTP_TRANSPORT_READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target = self.DataLinkReceive).start()
			self.PlayEvent = threading.Event()
			self.PlayEvent.clear()
			self.SendControlRequest("PLAY")
	
	def GetVideoParameter(self):
		'''
		描述：GetParameter操作
        参数：无
        返回：无
		'''	
		if self.Status == Constants.RTP_TRANSPORT_READY:
			self.SendControlRequest("GET_PARAMETER")

	def ChangeScaler(self, TheScalePlace):
		'''
		描述：滚动条变化事件
        参数：无
        返回：无
		'''	
		if self.Status != Constants.RTP_TRANSPORT_INIT:
			TheFrame = round(self.TotalFrameNumber * int(TheScalePlace) / self.ScalerValueMax)
			print("The File has loaded to the time of ", self.GetPlayTime(self.PictureFrame))
			print("The File has played to the time of ", self.GetPlayTime(self.PicturePlay))

			#进度条变化的足够大
			if abs(TheFrame - self.PicturePlay) > self.PicturePerSecond:
				self.PicturePlay = TheFrame
				self.UpdateProcess()
	
	def ChangePlaySpeed(self):
		'''
		描述：播放速率变化，处理播放速率选择事件
        参数：无
        返回：无
		'''	
		for i in range(len(self.PlaySpeedList)):
			if (self.IntVarChoiceValue.get() == i):
				self.CurrentPlaySpeed = self.PlaySpeedList[i][0]
				break 

	#控制连接相关函数，包括发送请求，处理收到的回复，处理请求等
	def SendControlRequest(self, TheRequestType):
		'''
		描述：向服务器发送控制请求
        参数：请求类型
        返回：无
		'''	
		if TheRequestType == "SETUP" and self.Status == Constants.RTP_TRANSPORT_INIT:
			threading.Thread(target = self.ReceiveControlReply).start()
			self.ControlSequence += 1
			
			TheRequest = 'SETUP ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) + \
			'\nTransport: RTP/UDP; client_port= ' + str(self.DataPort)
			self.RequestSent = "SETUP"
		
		elif TheRequestType == "GET_PARAMETER" and self.Status == Constants.RTP_TRANSPORT_READY:
			self.ControlSequence += 1
			TheRequest = 'GET_PARAMETER ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) \
			+ '\nSession: ' + str(self.Session)
			self.RequestSent = "GET_PARAMETER"

		elif TheRequestType == "PLAY" and self.Status == Constants.RTP_TRANSPORT_READY:
			self.ControlSequence += 1
			TheRequest = 'PLAY ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) \
			+ '\nSession: ' + str(self.Session)
			self.RequestSent = "PLAY"
		
		elif TheRequestType == "PAUSE" and self.Status == Constants.RTP_TRANSPORT_PLAYING:
			self.ControlSequence += 1
			TheRequest = 'PAUSE ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) \
			+ '\nSession: ' + str(self.Session)
			self.RequestSent = "PAUSE"

		elif TheRequestType == "RESUME" and self.Status == Constants.RTP_TRANSPORT_READY:
			self.ControlSequence += 1
			TheRequest = 'RESUME ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) \
			+ '\nSession: ' + str(self.Session)
			self.RequestSent = "RESUME"
			
		elif TheRequestType == "TEARDOWN" and not self.Status == Constants.RTP_TRANSPORT_INIT:
			self.ControlSequence += 1
			TheRequest = 'TEARDOWN ' + self.FileName + ' RTSP/1.0\n' \
			+ 'CSeq: ' + str(self.ControlSequence) \
			+ '\nSession: ' + str(self.Session)
			self.RequestSent = "TEARDOWN"
		else:
			return
		self.ControlSocket.send(TheRequest.encode())		
		print(TheRequest)
		print("-----------------------------")

	
	def ReceiveControlReply(self):
		'''
		描述：接收服务器的控制连接回复
        参数：无
        返回：无
		'''	
		while True:
			TheReply = self.ControlSocket.recv(Constants.CONTROL_SIZE)
			print(TheReply.decode("utf-8"))
			print("-----------------------------")
			if TheReply: 
				self.HandleControlReply(TheReply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.RequestSent == "TEARDOWN":
				try:
					self.ControlSocket.shutdown(socket.SHUT_RDWR)
					self.ControlSocket.close()
				except:
					donothing = True
				break
	
	def HandleControlReply(self, TheReply):
		'''
		描述：处理服务器的控制连接回复
        参数：回复内容
        返回：无
		'''	
		Lines = str(TheReply).split('\n')
		TheSequenceNum = int(Lines[1].split()[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if TheSequenceNum == self.ControlSequence:
			TheSession = int(Lines[2].split()[1])
			# New RTSP session ID
			if self.Session == Constants.UNDEFINED_NUMBER:
				self.Session = TheSession
			
			# Process only if the session ID is the same
			if self.Session == TheSession:
				if int(Lines[0].split()[1]) == Constants.STATUS_CODE_SUCCESS: 
					if self.RequestSent == "SETUP":
						self.Status = Constants.RTP_TRANSPORT_READY
						self.OpenDataPort()
						self.GetVideoParameter()
					elif self.RequestSent == "GET_PARAMETER":
						self.SetVideoParameter(str(TheReply))
						self.CreateScaler()
						self.PlayMovie()
					elif self.RequestSent == "PLAY":
						self.Status = Constants.RTP_TRANSPORT_PLAYING
					elif self.RequestSent == "PAUSE":
						self.Status = Constants.RTP_TRANSPORT_READY
						self.Pause["text"] = "Resume"
						self.Pause["command"] = self.ResumeMovie
						#self.PlayEvent.set()
					elif self.RequestSent == "RESUME":
						self.Status = Constants.RTP_TRANSPORT_PLAYING
						self.Pause["text"] = "Pause"
						self.Pause["command"] = self.PauseMovie
					elif self.RequestSent == "TEARDOWN":
						self.Status = Constants.RTP_TRANSPORT_INIT
						self.Valid = False

	#数据连接RTP部分：接收数据，更新帧，更新显示
	def DataLinkReceive(self):		
		'''
		描述：处理服务器的控制连接回复
        参数：回复内容
        返回：无
		'''	
		WhetherStartedPlay = False
		while True:
			try:
				TheData, TheAddress = self.DataSocket.recvfrom(Constants.DATA_PACKET_SIZE)
				#控制接收文件
				if TheData:
					ThePacket = RtpPacket()
					ThePacket.decode(TheData)
					
					CurrentSequenceNum = ThePacket.seqNum()
					CurrentMarker = ThePacket.Marker()

					#丢弃其余数据包
					if self.DataSequence == CurrentSequenceNum - 1:
						#print("received packet ", CurrentSequenceNum)
						#回复ACK
						ACKMessage = "ACK " + str(CurrentSequenceNum)
						self.DataSocket.sendto(ACKMessage.encode(), TheAddress)

						#判断是否新图片
						if CurrentMarker == 0:
							self.PictureFrame = self.PictureFrame + 1
							#print(self.PictureFrame)

						#写入
						self.DataSequence = CurrentSequenceNum
						self.WritePictureFrame(ThePacket.getPayload())

				#控制播放图片
				if self.PictureFrame - self.PicturePlay >= (self.PicturePerSecond * self.BufferTime):
					if WhetherStartedPlay == False:
						WhetherStartedPlay = True
						threading.Thread(target = self.UpdateMovie).start()

			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.PlayEvent.isSet(): 
					break
				
				#处理teardown事件
				if self.Valid == False:
					try:
						self.DataSocket.shutdown(socket.SHUT_RDWR)
						self.DataSocket.close()
					except:
						donothing = True
					break
					
	def WritePictureFrame(self, TheData):
		'''
		描述：写入图片帧
        参数：数据内容
        返回：无
		'''	
		TheCacheName = self.GetPictureCacheFileName(self.PictureFrame)
		File = open(TheCacheName, "ab")
		File.write(TheData)
		File.close()
	
	def UpdateMovie(self):
		'''
		描述：控制视频播放
        参数：文件名
        返回：无
		'''	
		while True:
			if self.Valid == False:
				break
			if self.Status != Constants.RTP_TRANSPORT_PLAYING:
				time.sleep(1 / self.PicturePerSecond)
				continue
			if self.PicturePlay >= self.PictureFrame:
				time.sleep(1 / self.PicturePerSecond)
				continue
			#print("The player has received ", self.PictureFrame, " frames")
			#print("The player has played ", self.PicturePlay, " frames")
			self.PicturePlay = self.PicturePlay + 1
			TheFileName = self.GetPictureCacheFileName(self.PicturePlay)
			try:
				self.UpdatePictureShow(TheFileName)
			except:
				donothing = True

			#更新进度条和时间显示
			self.UpdateScalerAndProcessWhenPlay()	
			time.sleep(1 / self.PicturePerSecond / self.CurrentPlaySpeed)

	def UpdatePictureShow(self, TheImageFileName):
		'''
		描述：更新图片显示
        参数：文件名
        返回：无
		'''	
		ThePhoto = ImageTk.PhotoImage(Image.open(TheImageFileName))
		self.Movie.configure(image = ThePhoto, height = 800) 
		self.Movie.image = ThePhoto
		
	def UpdateScalerAndProcessWhenPlay(self):
		'''
		描述：在播放中动态更新进度条和播放时间显示
        参数：无
        返回：无
		'''	
		CurrentProcess = round(self.PicturePlay / self.TotalFrameNumber * self.ScalerValueMax) 
		PreviousProcess = int(self.Scaler.get())
		if PreviousProcess != CurrentProcess:
			self.Scaler.set(CurrentProcess)
			CurrentLabelShow = self.GetPlayTime(self.PicturePlay) + '/' + self.GetPlayTime(self.TotalFrameNumber)
			self.ProgressShow.configure(text = CurrentLabelShow)

	def UpdateProcess(self):
		'''
		描述：更新播放时间显示
        参数：无
        返回：无
		'''	
		CurrentLabelShow = self.GetPlayTime(self.PicturePlay) + '/' + self.GetPlayTime(self.TotalFrameNumber)
		self.ProgressShow.configure(text = CurrentLabelShow)

	#基本操作函数，比如随机生成端口，生成完整文件名
	def GenerateRandomPort(self):	
		'''
		描述：生成随机的自身数据端口
		参数：无
		返回：一个随机数port
        '''
		ThePort = random.randint(10001, 65535)
		return ThePort

	def GetPictureCacheFileName(self, TheSequenceNum):
		'''
		描述：根据session，序列号，前缀等生成图片缓存文件名
		参数：序列号
		返回：文件名
        '''
		TheFileName = self.CacheDirPicture + '/' + self.CacheFront + str(self.Session)\
		 + '_' + str(TheSequenceNum) + self.PictureBack
		return TheFileName
	
	def SetVideoParameter(self, TheReply):
		'''
		描述：获取视频的总长度，帧率信息，用于设置自身属性
		参数：返回的报文
		返回：无
        '''
		#print(TheReply)
		Lines = str(TheReply).split('\n')
		#print(Lines[-1].split())
		TheFrameNumber = int(Lines[3].split()[1])
		TheFrameRate = int(Lines[3].split()[3])
		self.TotalFrameNumber = TheFrameNumber
		self.PicturePerSecond = TheFrameRate
	
	def GetPlayTime(self, TheFrameNumber):
		'''
		描述：根据播放帧数计算播放时间
		参数：帧数
		返回：字符串，代表时间
        '''
		TotalSecond = round(TheFrameNumber / self.PicturePerSecond)
		TheHour = floor(TotalSecond / 3600)
		TheMinute = floor((TotalSecond - TheHour * 3600) / 60)
		TheSecond = TotalSecond % 60
		TheString = str(TheHour) + ":" + str(TheMinute).zfill(2) + ":" + str(TheSecond).zfill(2)
		return TheString

if __name__ == "__main__":
	Root = Tk()
	TheClient = PlayClient(Root, Constants.SERVER_ADDR, Constants.SERVER_CONTROL_PORT, "test.mp4")
	Root.mainloop()
