#!/usr/bin/python2.7
#encoding=utf-8

import socket
from threading import Thread
import sys, time
import signal

SOCKTIMEOUT=5#客户端连接超时(秒)
RESENDTIMEOUT=300#转发超时(秒)

VER="\x05"
METHOD="\x00"

SUCCESS="\x00"
SOCKFAIL="\x01"
NETWORKFAIL="\x02"
HOSTFAIL="\x04"
REFUSED="\x05"
TTLEXPIRED="\x06"
UNSUPPORTCMD="\x07"
ADDRTYPEUNSPPORT="\x08"
UNASSIGNED="\x09"

_LOGGER=None

class Log:
	WARN="[WARN]"
	INFO="[INFO]"
	ERROR="[ERR]"
	def write(self,message,level):
		pass
		
class SimpleLog(Log):
	import sys
	def __init__(self,output=sys.stdout):
		self.__output=output
		self.show_log=True
		
	def write(self,message,level=Log.INFO):
		if self.show_log:
			self.__output.write("%s\t%s\n" %(level,message))
			
def getLogger(output=sys.stdout):
	global _LOGGER
	if not _LOGGER:
		_LOGGER=SimpleLog(output)
	return _LOGGER
		
class DSock():
    def __init__(self, sock, ip, port):
        self.ip = ip
        self.port = port
        self.sock = sock
        self.cnt = 0
    def add_cnt(self, cnt): self.cnt += cnt

class ReqPair():
    def __init__(self, sock, address):
        self.client_sock = sock
        self.client_addr = address
    def add_xxx(self): pass

class SocketTransform(Thread):
	def __init__(self,src,dest_ip,dest_port,bind=False):
		Thread.__init__(self)
		self.dest_ip=dest_ip
		self.dest_port=dest_port
		self.src=src
		self.bind=bind
		self.setDaemon(True)
        def close(self):
            self.sock.close()
            self.dest.close()

	def run(self):
		try:
			self.resend()
		except Exception,e:
			getLogger().write("Error on SocketTransform %s" %(e.message,),Log.ERROR)
			self.close()

	def resend(self):
		self.sock=self.src.client_sock
		self.dest=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.dest.connect((self.dest_ip,self.dest_port))
		if self.bind:
			getLogger().write("Waiting for the client")
			self.sock,info=sock.accept()
			getLogger().write("Client connected")
		#getLogger().write("Starting Resending")
		self.sock.settimeout(RESENDTIMEOUT)
		self.dest.settimeout(RESENDTIMEOUT)
                dest = DSock(self.dest,self.dest_ip, self.dest_port)
                src = DSock(self.sock, self.src.client_addr[0], self.src.client_addr[1])
		Resender(src, dest).start()
		Resender(dest, src).start()


class Resender(Thread):
	def __init__(self,src,dest):
		Thread.__init__(self)
		self.src=src
		self.setDaemon(True)
		self.dest=dest
                self.cnt = 0
                self.head = ''
        def close(self):
            self.src.sock.close()
            self.dest.sock.close()

        def debug(self):
            if self.src.port != 443 and self.dest.port != 443:
              print(self.src.ip, self.src.port, '>', self.dest.ip,self.dest.port, self.cnt, [self.head])
            else: print(self.src.ip, self.src.port, '>', self.dest.ip,self.dest.port, self.cnt, [self.head[:16]])

	def run(self):
		try:
			self.resend()
		except Exception,e:
			getLogger().write("con lost %s" %(e.message))
                        self.debug()
			self.close()

	def resend(self):
                t = time.time()
		data = self.src.sock.recv(64)
                if data:
                   self.cnt = len(data)
                   self.head = data
                   self.debug()
		while data:
                        if self.cnt/(time.time()-t) > 1000000:
                           print('rate', self.cnt/(time.time()-t))
                           #time.sleep(1)
			self.dest.sock.sendall(data)
			data = self.src.sock.recv(64)
                        self.cnt += len(data)
                        if self.cnt < 149:
                            self.head += data
		self.close()
		#getLogger().write("Client quit normally\n")
                self.debug()

def handle_sock4(req_pair, cd, byte3):
    sock = req_pair.client_sock
    b4,addr=sock.recv(1),sock.recv(4)
    dst_addr=".".join([str(ord(i)) for i in addr])
    dst_port = ord(b4)+(ord(byte3)<<8)
    print(dst_addr, dst_port)
    print [sock.recv(1)]
    sock.sendall('\x00'+'\x5a'+byte3+b4+addr)
    SocketTransform(req_pair,dst_addr,dst_port).start() 
    

def create_server(ip,port):
        conns = []
	transformer=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        transformer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	transformer.bind((ip,port))
	signal.signal(signal.SIGTERM,OnExit(transformer).exit)
	transformer.listen(1000)
	while True:
		sock,addr_info=transformer.accept()
		sock.settimeout(SOCKTIMEOUT)
		#getLogger().write("Got one client connection")
                print([addr_info])
                req_pair = ReqPair(sock, addr_info)
                #conns.append(req_pair)
		try:
			ver,nmethods,methods=(sock.recv(1),sock.recv(1),sock.recv(1))
                        print([ver,nmethods,methods])
                        if ver=='\x04': 
                           handle_sock4(req_pair, nmethods, methods)
                           continue
                        if ver == 'd':
                           handle_debug(req_pair, nmethods, methods)
                           continue
			sock.sendall(VER+METHOD)
			ver,cmd,rsv,atyp=(sock.recv(1),sock.recv(1),sock.recv(1),sock.recv(1))
                        print([ver,cmd,rsv,atyp])
			dst_addr=None
			dst_port=None
			if atyp=="\x01":#IPV4
				dst_addr,dst_port=sock.recv(4),sock.recv(2)
				dst_addr=".".join([str(ord(i)) for i in dst_addr])
			elif atyp=="\x03":#Domain
				addr_len=ord(sock.recv(1))#域名的长度
				dst_addr,dst_port=sock.recv(addr_len),sock.recv(2)
				dst_addr="".join([unichr(ord(i)) for i in dst_addr])
			elif atyp=="\x04":#IPV6
				dst_addr,dst_port=sock.recv(16),sock.recv(2)
				tmp_addr=[]
				for i in xrange(len(dst_addr)/2):
					tmp_addr.append(unichr(ord(dst_addr[2*i])*256+ord(dst_addr[2*i+1])))
				dst_addr=":".join(tmp_addr)
			dst_port=ord(dst_port[0])*256+ord(dst_port[1])
			getLogger().write("Client wants to connect to %s:%d" %(dst_addr,dst_port))
			server_sock=sock
			server_ip="".join([chr(int(i)) for i in ip.split(".")])

			if cmd=="\x02":#BIND
				#Unimplement
				sock.close()
			elif cmd=="\x03":#UDP
				#Unimplement
				sock.close()
			elif cmd=="\x01":#CONNECT
				sock.sendall(VER+SUCCESS+"\x00"+"\x01"+server_ip+chr(port/256)+chr(port%256))
				#getLogger().write("Starting transform thread")
				SocketTransform(req_pair,dst_addr,dst_port).start()
			else:#Unspport Command
				sock.sendall(VER+UNSPPORTCMD+server_ip+chr(port/256)+chr(port%256))
				sock.close()
		except Exception,e:
			getLogger().write("Error on starting transform:"+e.message,Log.ERROR)
			sock.close()

class OnExit:
	def __init__(self,sock):
		self.sock=sock

	def exit(self):
		self.sock.close()


if __name__=='__main__':
	try:
		ip="0.0.0.0"
		port=9051
		create_server(ip,port)
	except Exception,e:
		getLogger().write("Error on create server:"+e.message,Log.ERROR)



