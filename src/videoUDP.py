#####
# Redes 2
# Practica 3
# videoUDP.py
#
# Carlos Hojas García-Plaza y Sergio Cordero Rojas
#
# Se encuentran todas las funciones que se encarga del envio y recpecion UDP
#
#####

import queue
import socket
import cv2
from PIL import Image, ImageTk
import numpy as np
import time


class videoUDP:
	# puertos
	puerto_destino_UDP = None
	puerto_origen_UDP = None

	# IPs
	IP_destino = None
	IP_origen = None

	descriptor_captura = None
	video_path = None

	# sockets
	socket_envio = 0
	socket_recepcion = 0

	#buffers
	buffer_recepcion = None
	buffer_salida = None

	# cuanto menos sea mayor sera la compresion
	factor_compresion = 40

	# resolucion de envio
	ancho = 160
	alto = 120


	#####
	# Constructor de la clase
	#
	# IP_origen: IP del usuario conectado
	# puerto_origen_UDP: puerto de recepcion UDP del usuario conectado
	# buffer_recepcion: buffer de recpecion de frames
	# buffer_salida: buffer de envio de frames
	# FPS: frames por segundo
    #
	#####
	def __init__(self, IP_origen, puerto_origen_UDP, buffer_recepcion, buffer_salida, FPS):
		flag = False
		#creamos el socket de envio udp
		self.socket_envio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Socket de envio
		self.socket_envio.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		#creamos el socket de recepcion udp
		self.socket_recepcion = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Socket de recepcion
		#self.socket_recepcion.settimeout(5) # Timeout en el socket de 1 segundo
		self.socket_recepcion.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket_recepcion.bind(('0.0.0.0', int(puerto_origen_UDP))) # Asociamos el socket de recepcion al puerto correspondiente

		# Creamos un buffer de recepción que pueda guardar dos segundos de video
		self.buffer_recepcion = buffer_recepcion
		self.buffer_salida = buffer_salida
		self.FPS = FPS

		self.IP_origen = IP_origen
		self.puerto_origen_UDP = puerto_origen_UDP


	#####
	# Funcion que permite elegir la IP de destino y el puerto al cual
	# queremos conectarnos
    #
    # IP_destino: IP de destino a la que queremos conectarnos
    # puerto: puerto al que queremos conectarnos
    #
	#####
	def set_socket_envio(self, IP_destino, puerto_destino_UDP):
		self.IP_destino = IP_destino
		self.puerto_destino_UDP = puerto_destino_UDP

	#####
	# Funcion que permite elegir el numero de frames enviados por segundo
    #
    # nFrames: numero de frames que queremos comenzar a enviar por segundo
    #
	# return : True si se cambian los frames correctamente, False si no.
	#####
	def cambiar_FPS(self, n_Frames):

		if n_Frames > 0:
			self.FPS = n_Frames
			return True
		return False

	#####
	# Funcion que permite enviar un video, guardando en el campo de clase
	# correspondiente la ruta del video
    #
    # nFrames: numero de frames que queremos comenzar a enviar por segundo
    #
	# return : True si se cambian los frames correctamente, False si no.
	#####
	def enviar_video(self, path):
		if(path.is_file()):
			self.video_path = path;
			return True
		return False


	###########################################################################################################
    ################################## Funciones de envio de frames ###########################################
    ###########################################################################################################

	#####
	# Funcion que permite enviar un frame. Obtiene el frame del buffer de salida, le añade la cabecera y lo envía
    # al receptor.
    #
	#####
	def enviar_frame(self):

		# Sacamos un frame ya comprimido del buffer de salida
		if(not self.buffer_salida.full()):
			index,frame = self.buffer_salida.get()

		#Comprimimos el frame
		retVal, compressedFrame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.factor_compresion])

		# en caso de error devolvemos un None
		if(retVal == False):
			return None

		bFrame = compressedFrame.tobytes()
		# Creamos la cabecera
		cabecera = "{}#{}#{}x{}#{}#".format(index, time.time(), self.ancho, self.alto, self.FPS)
		bcabecera = cabecera.encode('utf-8')
		datos = bcabecera + bFrame # Concatenamos con el frame

		# Finalmente enviamos el frame con su cabecera al receptor
		self.socket_envio.sendto(datos, (self.IP_destino, int(self.puerto_destino_UDP)))

		return "OK"

	#####
	# Funcion que permite enviar frames al receptor en bucle, mientras no haya eventos que interrumpan
    # dicho flujo
	#
    # evento_pausa_UDP_udp: evento del hilo que permite pausar su ejecución de forma no definitiva
    # evento_final_llamada: evento del hilo que permite terminar con su ejecución definitivamente
    #
	#####
	def vaciar_buffer_salida(self, evento_final_llamada, evento_pausa_UDP):
		while not evento_final_llamada.is_set():
			while not evento_pausa_UDP.is_set():
				ret = self.enviar_frame()
				if ret == None:
					break
				if evento_final_llamada.is_set():
					self.buffer_salida.queue.clear()
					break
			if evento_final_llamada.is_set():
				break
		return


	###########################################################################################################
    ############################## Funciones de recepcion de frames ###########################################
    ###########################################################################################################

	#####
	# Funcion que permite recibir un frame. Para ello recibe un paquete por el socket,
	# desencapsula el frame y lo añade al buffer de recepcion
    #
	#####
	def recibir_frame(self):
		if self.socket_recepcion != None:
			mensaje, ip = self.socket_recepcion.recvfrom(80000)
		else:
			return
		# Comprobamos que la dirección ip de la que nos llega el paquete
		# es la que esperamos
		if ip[0] != self.IP_destino:
			return

		# Dividimos el mensaje por #, de modo que separamos los campos de la cabecera
		# y el contenido del paquete
		split = mensaje.split(b"#", 4)
		if not(self.buffer_recepcion.full()):
			# Insertamos el numero de orden junto con el frame comprimido
			self.buffer_recepcion.put((int(split[0]), mensaje))

		return


	#####
	# Funcion que permite recibir frames del emisor en bucle, mientras no haya eventos que interrumpan
    # dicho flujo
	#
    # evento_pausa_udp: evento del hilo que permite pausar su ejecución de forma no definitiva
    # evento_final_llamada: evento del hilo que permite terminar con su ejecución definitivamente
    #
	#####
	def llenar_buffer_recepcion(self, evento_final_llamada, evento_pausa_UDP):
		while not evento_final_llamada.is_set():
			while not evento_pausa_UDP.is_set():
				self.recibir_frame()
				if evento_final_llamada.is_set():
					break
			if evento_final_llamada.is_set():
				break
		return
