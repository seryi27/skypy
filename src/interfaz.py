#####
# Redes 2
# Practica 3
# interfaz.py
#
# Carlos Hojas García-Plaza y Sergio Cordero Rojas
#
# Se encuentran todas las funciones que interactuan con la interfaz
#
#####

# importamos todas las librerias necesarias
# interfaz
from appJar import gui
from PIL import Image, ImageTk
import numpy as np
import cv2
# clases del resto del programa
from src import ds
from src import controlTCP
from src import videoUDP
# varias
import subprocess
import threading
import os
import signal
from platform import system as get_os
import socket
import queue
import time


ruta = "./ficheros/config.txt"
comando = None


class interfaz(object):

	#Banderas para saber en que modo nos encontramos
	enLlamada = False
	enPausa = False
	sinRegistrar = True
	listaMostrada = False
	videoMostrado = False

	#instancias de las clases
	ds = None
	tcp = None
	udp = None

	#datos del usuario registrado
	usuario = None
	clave = None

	#IP y puertos del usuario registrado
	IP_origen = None
	puerto_origen_TCP = None
	puerto_origen_UDP = None

	# variables que obtenemos cuando recibimos un calling
	comando = None
	usuario_destino = None
	puerto_destino_UDP = None
	IP_destino = None


	# variables de mostrar frames
	buffer_count = 0
	dormir = 0.02
	FPS = 15
	inicio_llamada = 0
	frame_webcam = None

	# resoluciones de pantalla
	ancho_small = 160
	alto_small = 120
	ancho_big = 640
	alto_big = 480

	# Eventos para controlar el envio y la recepcion de video por UDP
	evento_pausa_UDP = None
	evento_final = None
	evento_final_llamada = None

	#hilos
	hilo_escucha_llamada = None
	hilo_escucha_calling = None
	hilo_envio_UDP = None
	hilo_recepcion_UDP = None
	hilo_mostrar_frames = None

	# indice para numerar los frames
	index = 0

	#####
	# Constructor de la clase
	#
	# window_size : tamaño de pantalla
    #
	#####
	def __init__(self, window_size):

		# Creamos una variable que contenga el GUI principal
		self.app = gui("Redes2 - P2P", window_size)
		self.app.setGuiPadding(10,10)

		# Preparación del interfaz
		self.app.addLabel("title", "Cliente Multimedia P2P - Redes2")
		self.app.addImage("video", "imgs/webcam.gif")

		# Registramos la función de captura de video
		# Esta misma función también sirve para enviar un vídeo
		if get_os() == "Windows":
			self.cap = cv2.VideoCapture(0)
		else:
			self.cap = cv2.VideoCapture("DJI_20190416_212830")

		self.app.setPollTime(round(1000/self.FPS))
		self.app.registerEvent(self.capturaVideo)

		# Añadimos los botones
		self.app.addButtons(["BotonA", "BotonB", "BotonC", "BotonD"], self.buttonsCallback)
		self.app.setButton("BotonA","Llamar")
		self.app.setButton("BotonB","Listar Usuarios")
		self.app.setButton("BotonC","Informacion de Usuarios")
		self.app.setButton("BotonD","Iniciar Sesion")

		# Barra de estado
		# Debe actualizarse con información útil sobre la llamada (duración, FPS, etc...)
		self.app.addStatusbar(fields=2)

		self.buffer_recepcion = queue.PriorityQueue(self.FPS*2)
		self.buffer_salida = queue.PriorityQueue(self.FPS*2)

		# Instanciamos las clase del servidor de descubrimiento
		self.ds = ds.servidorDescubrimiento()

		# Obtenemos los puertos y la IP del fichero de configuracion
		try:
			with open(ruta, "r") as fihcero_config:
				mensaje = fihcero_config.read()
				datos = mensaje.split(' ')
				self.puerto_origen_UDP = datos[0].split(":")[1]
				self.puerto_origen_TCP = datos[1].split(":")[1]
		except FileNotFoundError:
			print("Error en el fcihero de configuracion")

		self.IP_origen = self.conseguir_IP()

	#####
	# Funcion que obtiene la IP
    #
	# return : IP del usuario
	#####
	def conseguir_IP(self):
		socket_IP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			socket_IP.connect(('10.255.255.255',1))
			IP = socket_IP.getsockname()[0]
		except Exception as e:
			IP = '127.0.0.1'
		finally:
			socket_IP.close()
		return IP


	#####
	# Funcion que se encarga de iniciar la interfaz
    #
	#####
	def start(self):
		if get_os() == 'Windows':
			signal.signal(signal.SIGINT, self.SIGUSR1_handler)
		else:
			signal.signal(signal.SIGUSR1,self.SIGUSR1_handler)

		self.app.go()

###########################################################################################################
#######################  Funcion para manejar los eventos en la interfaz  #################################
###########################################################################################################


	#####
	# Función que gestiona los botones de la lista
	#
	#####
	def buttonList(self, button):
		if button == "Llamar":
			usuario = self.app.getListBox("Usuarios encontrados")
			ret = self.ds.query_usuario(usuario[0])
			if ret == None:
				self.app.errorBox("Error de Buscar Informacion de Usuario", "Error del servidor", parent=None)
			elif ret == "Error de conexion":
				self.app.errorBox("Error de Servidor", ret, parent=None)
			else:
				self.send_calling(IP_destino = ret.IP, puerto_destino_TCP = ret.puerto)
				self.app.hideSubWindow("List")
		else:
			self.app.hideSubWindow("List")


	#####
	# Función que gestiona las acciones de los botones principales de interfaz
	#
	#####
	def buttonsCallback(self, button):
		if button == "BotonA":
			if self.sinRegistrar:
				self.app.errorBox("Error", "Debes iniciar sesion para ejecutar esta acción", parent=None)
				return
			# a partir de aqui estaremos registrados
			elif self.enLlamada and self.enPausa == False: #PAUSAR
				# mandamos el hold al otro usuario y comprobamos si el otro usuario ha perdido la conexion
				ret = self.tcp.hold(self.usuario)
				if ret == "Aborted":
					self.app.errorBox("Error de Conexion", "El otro usuario ha perdido la conexion", parent=None)
					self.cerrarConexionTCP()
					return
				self.cambiarPausa()
				return
			elif self.enPausa: #REANUDAR
				# mandamos el resume al otro usuario y comprobamos si el otro usuario ha perdido la conexion
				ret = self.tcp.resume(self.usuario)
				if ret == "Aborted":
					self.app.errorBox("Error de Conexion", "El otro usuario ha perdido la conexion", parent=None)
					self.cerrarConexionTCP()
					return
				self.cambiarLlamada()
				return
			else: #LLAMAR
				usuario = self.app.textBox("Call", "Introduce el nick del usuario que deseas llamar", parent=None)
				if usuario == None:
					self.app.errorBox("Error de Buscar Informacion de Usuario", "Debe introducir un usuario", parent=None)
					return
				# obtenemos la informacion del usuario controlando errores
				ret = self.ds.query_usuario(usuario)
				if ret == None:
					self.app.errorBox("Error de Buscar Informacion de Usuario", "Error del servidor", parent=None)
				elif ret == "Error de conexion":
					self.app.errorBox("Error de Servidor", ret, parent=None)
				else:
					self.send_calling(IP_destino = ret.IP, puerto_destino_TCP = ret.puerto)


		if button == "BotonB" :
			if self.sinRegistrar:
				self.app.errorBox("Error", "Debes iniciar sesion para ejecutar esta accion", parent=None)
				return
			if self.enLlamada == False and self.enPausa == False: #LISTAR_USUARIOS
				# obtenemos la lista de usuarios y la mostramos en caso de que no haya errores
				ret = self.ds.listar_usuarios()
				nicks = self.ds.parsear_usuarios(ret)
				if ret == None:
					self.app.errorBox("Error de Listar Usuario", "Error del servidor", parent=None)
				elif ret == "Error de conexion":
					self.app.errorBox("Error de Servidor", ret, parent=None)
				else:
					self.mostrarLista(nicks)
			else: #COLGAR
				# enviamos el end al otro usuario y cerramos la conexion
				ret = self.tcp.end(self.usuario)
				self.cerrarConexionTCP()
				self.evento_final_llamada.set()

		if button == "BotonC":
			if self.sinRegistrar == True:
				self.app.errorBox("Error", "Debes iniciar sesion para ejecutar esta accion", parent=None)

			elif self.enLlamada == False and self.enPausa == False and self.sinRegistrar==False: #INFO USUARIO
				# obtenemos la informacion del usuario y la mostramos si no hay error
				usuario = self.app.textBox("Search", "Introduce el nick del usuario que deseas buscar", parent=None)
				ret = self.ds.query_usuario(usuario)
				if ret == None:
					self.app.errorBox("Error de Buscar Informacion de Usuario", "Error del servidor", parent=None)
				elif ret == "Error de conexion":
					self.app.errorBox("Error de Servidor", ret, parent=None)
				else:
					self.app.infoBox("Informacion Del usuario "+usuario , "Usuario: {}, Direccion IP: {}, Puerto: {}, Protocolos: {} ".format(
					ret.nick , ret.IP , ret.puerto, ret.versiones), parent = None )
			else:
				self.app.errorBox("Error", "Debes colgar primero la llamada para ejecutar esta accion.", parent=None)

		if button == "BotonD":
			if self.sinRegistrar:
				ret = self.login()
			# a partir de aqui estamos logeados
			elif self.enPausa or self.enLlamada: #CERRAR SESION
				self.app.errorBox("Error", "Debes colgar primero la llamada para ejecutar esta accion.", parent=None)
			elif self.sinRegistrar == False:
				if self.tcp.socket_recepcion != None:
					self.tcp.socket_recepcion.close()
				self.tcp.socket_recepcion = None
				self.cambiarNoLogeado()


###########################################################################################################
########################  Funciones para cambiar el modo de la interfaz ###################################
###########################################################################################################

	#####
	# Funcion que se encarga de iniciar sesion
    #
	# return : Ok si el usuario se ha logueado correctamente o None en caso de error
	#####
	def login(self):
		#Pedimos los datos para logearnos
		ret = self.app.yesNoBox("Login","Desea cambiar el puerto TCP, el puerto UDP y la IP asignadas por defecto")
		if ret == True:
			self.puerto_origen_TCP = self.app.textBox("Login", "Introduce tu puertoTCP", parent=None)
			if self.puerto_origen_TCP == None:
				self.app.errorBox("Error de Inciar Sesion", "Debe introducir un puerto", parent=None)
				return
			self.puerto_origen_UDP = self.app.textBox("Login", "Introduce tu puertoUDP", parent=None)
			if self.puerto_origen_UDP == None:
				self.app.errorBox("Error de Inciar Sesion", "Debe introducir un puerto", parent=None)
				return
			self.IP_origen = self.app.textBox("Login", "Introduce tu direccion IP", parent=None)
			if self.IP_origen == None:
				self.app.errorBox("Error de Inciar Sesion", "Debe introducir una IP", parent=None)
				return
		self.usuario = self.app.textBox("Login", "Introduce el nombre de usuario", parent=None)
		if self.usuario == None:
			self.app.errorBox("Error de Buscar Informacion de Usuario", "Debe introducir un usuario", parent=None)
			return
		elif self.usuario.count('#') != 0:
			self.app.errorBox("Error de Buscar Informacion de Usuario", "No puede introducir caracteres especiales", parent=None)
			return
		self.clave = self.app.textBox("Login", "Introduce la contraseña", parent=None)
		if self.clave == None:
			self.app.errorBox("Error de Buscar Informacion de Usuario", "Debe introducir una clave", parent=None)
			return


		# nos logueamos y controlamos los posibles errores
		ret = self.ds.login(self.usuario, self.clave, self.IP_origen, self.puerto_origen_TCP)
		if ret != "OK":
			self.app.errorBox("Error de Inicio de Sesion", ret, parent=None)
		else:
			# inicializamos la clase que se encarga de la conexion TCP entre pares de usuario
			self.tcp = controlTCP.controlTCP(self.puerto_origen_UDP, self.puerto_origen_TCP, self.IP_origen)
			# inicializamos el hilo de escucha de peticiones calling y lo lanzamos
			self.evento_final = threading.Event()
			self.hilo_escucha_calling = threading.Thread(target= self.puerto_escucha_calling, args=(self.evento_final, ), daemon=True)
			self.hilo_escucha_calling.start()
			self.app.infoBox("LogIn", "Sesion inicada correctamente", parent=None)
			self.cambiarLogeado()

			# print_control
			print("Registrado con IP: {}, UDP: {}, TCP: {}".format(self.IP_origen, self.puerto_origen_UDP, self.puerto_origen_TCP))

	#####
	# Funcion que se encarga de cambiar la pestaña al modo llamada
    #
	#####
	def cambiarLlamada(self):
		self.enPausa = False
		self.enLlamada = True
		self.app.setButton("BotonA","Pausar")
		self.app.setButton("BotonB","Colgar")
		self.app.setLabel("title", "En llamada con {}".format(self.usuario_destino))
		return

	#####
	# Funcion que se encarga de cambiar la pestaña al modo pausa
    #
	#####
	def cambiarPausa(self):
		self.enLlamada = True
		self.enPausa = True
		self.app.setButton("BotonA","Reanudar")
		self.app.setButton("BotonB","Colgar")
		self.app.setLabel("title", "La llamada con {} esta pausada".format(self.usuario_destino))
		return

	#####
	# Funcion que se encarga de cambiar la pestaña al modo de pantalla principal de logueado
    #
	#####
	def cambiarLogeado(self):
		self.enLlamada = False
		self.enPausa = False
		self.sinRegistrar = False
		self.app.setButton("BotonA", "Llamar")
		self.app.setButton("BotonB", "Listar Usuarios")
		self.app.setButton("BotonD","Cerrar Sesion")
		self.app.setLabel("title", "Bienvenido {}".format(self.usuario))
		self.app.setStatusbar(" ",1)
		return

	#####
	# Funcion que se encarga de cambiar la pestaña al modo de pantalla principal de no logueado
    #
	#####
	def cambiarNoLogeado(self):
		self.enLlamada = False
		self.enPausa = False
		self.sinRegistrar = True
		self.app.setButton("BotonD","Iniciar Sesion")
		self.app.setLabel("title", "Cliente Multimedia P2P - Redes2")
		return

	#####
	# Funcion que se encarga de mostrar la lista de usuarios encontrados
    #
	#####
	def mostrarLista(self, nicks):
		if self.listaMostrada == False:
			self.app.startSubWindow("List",modal=True)
			self.app.addListBox("Usuarios encontrados", nicks)
			self.app.addButton("Cerrar", self.buttonList)
			self.app.addButton("Llamar", self.buttonList)
			self.app.stopSubWindow()
			self.app.showSubWindow("List")
			self.listaMostrada = True
		else:
			self.app.showSubWindow("List")

	#####
	# Funcion que se encarga de cerrar la conexion TCP
    #
	#####
	def cerrarConexionTCP(self):
		if self.tcp.socket_conexion != None:
			self.tcp.socket_conexion.close()
		self.tcp.socket_conexion = None
		self.evento_final.set()
		self.cambiarLogeado()


###########################################################################################################
############################   Funciones para capturar y mostrar video  ###################################
###########################################################################################################

	#####
	# Función que captura el frame a mostrar en cada momento y lo mete en el buffer de envio
	#
	#####
	def capturaVideo(self):
		#Capturamos un frame de la cámara o del vídeo
		ret, self.frame_webcam = self.cap.read()

		# si no estamos en llamada lo mostramos en la interfaz
		if self.enLlamada == False:
			frame_big = cv2.resize(self.frame_webcam, (640,480))
			cv2_im = cv2.cvtColor(frame_big,cv2.COLOR_BGR2RGB)
			img_tk = ImageTk.PhotoImage(Image.fromarray(cv2_im))
			self.app.setImageData("video", img_tk, fmt = 'PhotoImage')

		# si estamos en una llamada que no esta en pausa lo metemos en el buffer de envio
		if(self.enLlamada and self.enPausa == False):
			self.index += 1
			self.buffer_salida.put((self.index,self.frame_webcam))

	#####
	# Funcion que permite mostrar un frame que obtenemos desde el buffer de recepcion.
    #
	#####
	def sacar_frame_buffer(self):

		# si el buffer esta vacio salimos
		if self.buffer_recepcion.empty():
			return

		# control de flujo
		time.sleep(self.dormir)
		if self.buffer_recepcion.qsize() < self.FPS:
			self.dormir *= 1.05
		elif self.buffer_recepcion.qsize() > self.FPS:
			self.dormir *= 0.95

		# si se ha llenado la cola la vaciamos
		if self.buffer_recepcion.full():
			self.buffer_recepcion.queue.clear()

		# sacamos un paquete del buffer
		paquete = self.buffer_recepcion.get()[1]

		# separamos los parametros de la cabecera y el frame codificado
		parametros = paquete.split(b'#',4)

		# cogemos un frame de la webcam
		frame_small = cv2.resize(self.frame_webcam, (self.ancho_small, self.alto_small))

		# cogemos un frame del buffer de recepcion
		frame_base = cv2.resize(cv2.imdecode(np.frombuffer(parametros[4],np.uint8), 1), (self.ancho_big, self.alto_big))

		# mezclamos ambos frames para mostrarlos
		frame_compuesto = frame_base
		frame_compuesto[0:frame_small.shape[0], 0:frame_small.shape[1]] = frame_small

		# imprimimos el frame compuesto
		frame_compuesto = cv2.cvtColor(frame_compuesto,cv2.COLOR_BGR2RGB)
		img_tk = ImageTk.PhotoImage(Image.fromarray(frame_compuesto))
		self.app.setImageData("video", img_tk, fmt = 'PhotoImage')
		self.videoMostrado = True

		self.app.setStatusbar("Tiempo de llamada: {0:.2f}".format(time.time()-self.inicio_llamada), 1)

		return

	#####
	# Funcion que muestra los frames sacados del buffer de reordenacion por pantalla mientras no se interrumpa el flujo
	#
	# evento_pausa_UDP: evento del hilo que permite pausar su ejecución de forma no definitiva
    # evento_final_llamada: evento del hilo que permite terminar con su ejecución definitivamente
	#
	#####
	def mostrar_video(self, evento_final_llamada, evento_pausa_UDP):
		while not evento_final_llamada.is_set():
			while not evento_pausa_UDP.is_set():
				self.sacar_frame_buffer()
				# si nos encontramos en pausa vaciamos la cola de recpecion
				if evento_pausa_UDP.is_set():
					self.buffer_recepcion.queue.clear()
				# si han finalizado la llamada vaciamos los buffer y terminamos la funcion y con ello la ejecucion del hilo
				if evento_final_llamada.is_set():
					self.buffer_recepcion.queue.clear()
					self.buffer_salida.queue.clear()
					break
			if evento_final_llamada.is_set():
				break
		self.app.setStatusbar(" ", 1)
		return

	#####
	# Funcion que establece la resolución de la imagen capturada
	#
	#####
	def setImageResolution(self, resolution):
		# Se establece la resolución de captura de la webcame
		# Puede añadirse algún valor superior si la cámara lo permite
		# pero no modificar estos
		if resolution == "LOW":
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)
		elif resolution == "MEDIUM":
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
		elif resolution == "HIGH":
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)



###########################################################################################################
############################   Funciones para enviar peticiones ###########################################
###########################################################################################################
	#####
	# Funcion que realiza la peticion de una llamada, crea el socket y el hilo que gestiona los comandos de control de dicha llamada.
	#
	# IP_destino: IP del receptor de la peticion
    # puerto_destino_TCP: puerto TCP al que enviamos la peticion
	#
	#####
	def send_calling(self, IP_destino, puerto_destino_TCP):
		#establecemos el socket por el que vamos a conectarnos con el otro usuario
		try:
			# print_control
			print("IP_destino : " + IP_destino)
			print("puerto_destino_TCP : " + puerto_destino_TCP)
			self.tcp.socket_conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.tcp.socket_conexion.connect((IP_destino, int(puerto_destino_TCP)))
		except (ConnectionError, OSError):
		 	self.app.infoBox("Usuario no conectado", "El usuario no esta conectado, intentelo de nuevo mas tarde", parent=None)
		 	return

		# inicializamos el hilo  y le asociamos la funcion que escucha los comandos CALLING
		self.evento_final_llamada = threading.Event()
		self.hilo_escucha_llamada = threading.Thread(target= self.puerto_escucha_llamada, args=(self.evento_final_llamada, ), daemon=True)
		self.hilo_escucha_llamada.start()

		# mandamos el calling
		ret2 = self.tcp.calling(usuario = self.usuario)

	#####
	# Funcion que manda un CALLING_ACCEPTED, crea el socket y el hilo que gestiona los comandos de control de dicha llamada.
	#
	# IP_destino: IP del receptor de la peticion
    # puerto_destino_TCP: puerto TCP al que enviamos la peticion
	#
	#####
	def send_calling_acepted(self, IP_destino, puerto_destino_TCP):
		self.tcp.call_accepted(usuario = self.usuario)
		self.enLlamada = True

		#Inicializamos el hilo que escucha las peticiones TCP de la llamada (resume, hold, end)
		self.evento_final_llamada = threading.Event()
		self.hilo_escucha_llamada = threading.Thread(target= self.puerto_escucha_llamada, args=(self.evento_final_llamada, ), daemon=True)
		self.hilo_escucha_llamada.start()

		# inicializamos la clase de UDP
		self.udp = videoUDP.videoUDP(self.IP_origen, self.puerto_origen_UDP, self.buffer_recepcion, self.buffer_salida, self.FPS)
		self.udp.set_socket_envio(IP_destino = self.IP_destino , puerto_destino_UDP = self.puerto_destino_UDP)

		# establecemos los eventos para pausar y terminar la ejecucion de los hilos
		self.evento_pausa_UDP = threading.Event()
		self.evento_final_llamada = threading.Event()

		# Inicializamos los hilos udp tanto de envio como de recepcion de frames, asi como otro para mostrar los frames
		self.hilo_recepcion_UDP = threading.Thread(target= self.udp.llenar_buffer_recepcion, args = (self.evento_final_llamada, self.evento_pausa_UDP,),daemon = True)
		self.hilo_envio_UDP = threading.Thread(target= self.udp.vaciar_buffer_salida, args = (self.evento_final_llamada, self.evento_pausa_UDP,), daemon = True)
		self.hilo_mostrar_frames = threading.Thread(target= self.mostrar_video, args = (self.evento_final_llamada, self.evento_pausa_UDP,), daemon = True)

		# Comenzamos a ejecutar los hilos
		self.hilo_recepcion_UDP.start()
		self.hilo_envio_UDP.start()
		self.hilo_mostrar_frames.start()

		# guardamos el tiempo en el que se inicio la llamada
		self.inicio_llamada = time.time()

		self.cambiarLlamada()


###########################################################################################################
############################   Funciones para manejar peticiones ##########################################
###########################################################################################################

	#####
	# Funcion que gestiona la peticion de una llamada entrante. Preguntamos el usuario si quiere aceptar y envia la respuesta.
	#
	#
	#####
	def calling_control(self):

		# obtenemos la informacion del usuario que nos ha enviado la peticion
		informacion_usuario = self.ds.query_usuario(self.usuario_destino)
		self.IP_destino = informacion_usuario.IP
		self.puerto_destino_TCP = informacion_usuario.puerto

		mensaje = "Llamada entrante de {} ¿Quieres aceptarla?".format(self.usuario_destino)
		respuesta = self.app.yesNoBox("LLamada entrante", mensaje, parent=None)

		# si la respuesa es que no, cerramos la conexion y enviamos un CALL_DENIED
		if respuesta == False:
			self.tcp.call_denied(usuario = self.usuario)
			self.tcp.socket_conexion.close()
			self.tcp.socket_conexion = None
		# si la respuesta es afirmativa llamamos a la funcion que gestiona el envio de un calling CALL_ACCEPTED
		elif respuesta == True:
			self.send_calling_acepted(self.IP_destino, self.puerto_destino_TCP)


	#####
	# Funcion que gestiona la recepcion de un CALL_ACCEPTED. .
	#
	#
	#####

	def call_accepted_control(self):
		# obtenemos la informacion del usuario que nos ha respondido
		informacion_usuario = self.ds.query_usuario(self.usuario_destino)
		self.IP_destino = informacion_usuario.IP

		# mostramos una ventana informando al usuario
		mensaje = "{} ha aceptado tu llamada!".format(self.usuario_destino)
		self.app.infoBox("LLamada establecida", mensaje, parent=None)
		self.enLlamada = True

		# instanciamos la clase que se encarga de UDP
		self.udp = videoUDP.videoUDP(self.IP_origen, self.puerto_origen_UDP, self.buffer_recepcion, self.buffer_salida, self.FPS)
		self.udp.set_socket_envio(IP_destino = self.IP_destino , puerto_destino_UDP = self.puerto_destino_UDP)

		# establecemos los eventos apra pausar y finalizar los hilos
		self.evento_pausa_UDP = threading.Event()
		self.evento_final_llamada = threading.Event()

		# Inicializamos los hilos udp tanto de envio como de recepcion, asi como otro para mostrar los frames
		self.hilo_recepcion_UDP = threading.Thread(target= self.udp.llenar_buffer_recepcion, args = (self.evento_final_llamada, self.evento_pausa_UDP,),daemon = True)
		self.hilo_envio_UDP = threading.Thread(target= self.udp.vaciar_buffer_salida, args = (self.evento_final_llamada, self.evento_pausa_UDP,), daemon = True)
		self.hilo_mostrar_frames = threading.Thread(target= self.mostrar_video, args = (self.evento_final_llamada, self.evento_pausa_UDP,), daemon = True)

		# Comenzamos a ejecutar los hilos
		self.hilo_recepcion_UDP.start()
		self.hilo_envio_UDP.start()
		self.hilo_mostrar_frames.start()

		# guardamos el tiempo en el que se inicio la llamada
		self.inicio_llamada = time.time()

		self.cambiarLlamada()


	#####
	# Funcion que gestiona la recepcion de un CALL_DENIED. Informamos al usuario de que le han rechazado la peticion de llamada.
	#
	#
	#####
	def call_denied_control(self):
		mensaje = "{} no ha aceptado tu llamada.".format(self.usuario_destino)
		self.app.infoBox("LLamada denegada", mensaje, parent=None)
		self.evento_final_llamada.set()

	#####
	# Funcion que gestiona la recepcion de un CALL_HOLD. Informamos al usuario de que le han pausado la llamada.
	#
	#
	#####
	def call_hold_control(self):
		mensaje = "{} ha pausado la llamada.".format(self.usuario_destino)
		self.app.infoBox("LLamada pausada.", mensaje, parent=None)
		self.cambiarPausa()
		self.evento_pausa_UDP.set()

	#####
	# Funcion que gestiona la recepcion de un CALL_RESUME. Informamos al usuario de que le han reanudado la llamada.
	#
	#
	#####
	def call_resume_control(self):
		mensaje = "{} ha reanudado la llamada.".format(self.usuario_destino)
		self.app.infoBox("LLamada reanudada.", mensaje, parent=None)
		self.cambiarLlamada()

	#####
	# Funcion que gestiona la recepcion de un CALL_END. Informamos al usuario de que le han finalizado la llamada.
	#
	#
	#####
	def call_end_control(self):
		mensaje = "{} ha finalizado la llamada.".format(self.usuario_destino)
		self.app.infoBox("LLamada finalizada.", mensaje, parent=None)
		self.cambiarLogeado()
		self.evento_final_llamada.set()

	#####
	# Funcion que trata las peticiones de calling
	#
	# evento_final: evento que se utilizara para la finalizacion del hilo de escucha
	#
	#####
	def puerto_escucha_calling(self, evento_final):
		# mientras no cerremos la conexion
		while not evento_final.is_set():
			if self.tcp.socket_recepcion == None:
				break
			# hacemos un accept para establecer conexion con el otro usuario
			try:
				socket, direccion = self.tcp.socket_recepcion.accept()
			except (ConnectionError, OSError):
				break
			# si nos encontramos en una llamada enviamos un CALL_BUSY
			if self.enLlamada:
				self.tcp.call_busy(socket)
				return
			# si no estamos en la llamada guardamos el socket
			self.tcp.socket_conexion = socket
			# obtenemos la peticion que nos han mandado y los campos
			peticion = self.tcp.socket_conexion.recv(2048).decode('ASCII')

			# print_control
			print(peticion)

			datos = peticion.split(" ")

			self.comando = datos[0]
			self.usuario_destino = datos[1]
			self.puerto_destino_UDP = datos[2]
			# lanzamos la señal para que el hilo principal
			self.lanzar_SIGUSR1()

	#####
	# Funcion que trata las peticiones de calling_hold, calling_resume y calling_end
	#
	# evento_final_llamada: se utilizara para la finalizacion del hilo
	#
	#####
	def puerto_escucha_llamada(self, evento_final_llamada):
		# mientras no cerremos la conexion
		while not evento_final_llamada.is_set():
			# intentamos leer del socket
			try:
				peticion = self.tcp.socket_conexion.recv(2048).decode('utf-8')
				if peticion == '':
					self.cerrarConexionTCP()
					if self.evento_final_llamada != None:
						self.evento_final_llamada.set()
					self.app.infoBox("Error", "El otro usuario ha perdido la conexion", parent = None)
					break
			except (ConnectionError, OSError):
				self.cerrarConexionTCP()
				if self.evento_final_llamada != None:
					self.evento_final_llamada.set()
					self.app.infoBox("Error", "El otro usuario ha perdido la conexion", parent = None)
				break

			# print_control
			print(peticion)

			# obtenemos la peticion que nos han mandado y los campos
			datos = peticion.split(" ")

			self.comando = datos[0]
			# si recibimos un call bussy informamos al usuario y cerramos la conexion
			if self.comando == "CALL_BUSY":
				self.app.infoBox("Usuario Ocupado", "El usuario se encuentra en otra llamada", parent=None)
				self.lanzar_SIGUSR1()
				self.cerrarConexionTCP()
				self.evento_final_llamada.set()
				break
			# en caso de no ser un call bussy tambien recibimos el usuario que lo envia
			self.usuario_destino = datos[1]
			# si recibimos un CALL_END o CALL_DENIED cerramos la conexion e informamos al hilo principal
			if self.comando == "CALL_END" or self.comando == "CALL_DENIED":
				self.tcp.socket_conexion.close()
				self.tcp.socket_conexion = None
				self.lanzar_SIGUSR1()
				break
			# en caso de recibir un CALL_ACCEPTED obtenemos el usuario que lo envio e informamos al hilo principal
			if self.comando == "CALL_ACCEPTED":
				self.puerto_destino_UDP = datos[2]
			self.lanzar_SIGUSR1()

	#####
	# Funcion que lanza la señal dependiendo del sistema operativo en el que nos encontremos
	#
	#####
	def lanzar_SIGUSR1(self):
		if get_os() == 'Windows':
			os.kill(os.getpid(), signal.CTRL_C_EVENT)
		else:
			os.kill(os.getpid(), signal.SIGUSR1)


###########################################################################################################
######################################    HANDLERS PARA SEÑALES    ########################################
###########################################################################################################

	#####
	# Handler de la señal enviada por los hilos de escucha. En funcion del comando ejecuta una controlador diferente.
	#
	#####
	def SIGUSR1_handler(self, signum, frame):
		if self.comando == "CALLING":
			self.calling_control()
		elif self.comando == "CALL_HOLD":
			self.call_hold_control()
		elif self.comando == "CALL_RESUME":
			self.call_resume_control()
		elif self.comando == "CALL_END":
			self.call_end_control()
		elif self.comando == "CALL_ACCEPTED":
			self.call_accepted_control()
		elif self.comando == "CALL_DENIED":
			self.call_denied_control()
