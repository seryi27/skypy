#####
# Redes 2
# Practica 3
# controlTCP.py
#
# Carlos Hojas García-Plaza y Sergio Cordero Rojas
#
# Se encuentran todas las funciones que se encargan de la interaccion con el servidor de descubirimiento
#
#####

import socket
import time
from src import user


class servidorDescubrimiento:

	#####
	# En esta clase vamos a realizar las funciones relacionadas con el servidor de descubrimiento, tales como
	# register, query, list and quit
	#####

	host = "vega.ii.uam.es"
	puerto = 8000
	buffer = 1024

	#####
	# Constructor de la clase
	#
	#####
	def __init__(self):
		return

	#####
	# Funcion que se encarga de crear un socket TCP, el cual se conecta con el servidor de descubrimiento
	#
	# return : el sockect creado o None en caso de error
	#####
	def abrir_conexion(self):
		if self.puerto == None:
			return None
		try:
			conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			conexion.connect((self.host,int(self.puerto)))
		except (OSError, ConnectionError):
			return None

		return conexion


	#####
	# Funcion que se encarga de registrar un usuario el servidor de descubrimiento
	# o que inicia sesion en caso de que el usuario ya este registrado
	#
	# usuario: nombre del usuario
	# direccionIP: direccion IP del usuario
	# puerto: puerto del usuario
	# clave: contraseña del usuario
	#
	# return : OK si se ha registrado/logeado el usuario o None en caso de error
	#####
	def login(self, usuario, clave, direccionIP, puertoTCP):
		conexion = self.abrir_conexion()

		if conexion == None:
			return "Error de conexion"

		#construimos la peticion de registro y la enviamos
		peticion = "REGISTER {} {} {} {} V1".format(usuario, direccionIP, puertoTCP, clave)
		conexion.send(bytes(peticion, encoding = 'utf-8'))

		respuesta = conexion.recv(self.buffer).decode('utf-8')
		self.cerrar_conexion(conexion)

		#tratamos la respuesta enviada por el servidor
		if respuesta == "NOK SYNTAX_ERROR":
			return "ERROR. Peticion mal formulada"

		elif respuesta == "NOK WRONG_PASS":
			return "ERROR. Contraseña incorrecta"
		else:
			return "OK"


	#####
	# Funcion que permite obtener la dirección IP y puerto de un usuario conociendo su nick
	#
	# usuario: nombre del usuario del que queremos obtener los datos
	#
	# return : diccionario con los datos del usuario o None en caso de error
	#####
	def query_usuario(self, usuario):
		conexion = self.abrir_conexion()

		if conexion == None:
			return "Error de conexion"

		#construimos la peticion de query y la enviamos
		peticion = "QUERY {}".format(usuario)
		conexion.send(bytes(peticion, encoding = 'utf-8'))

		respuesta = conexion.recv(self.buffer).decode('utf-8')
		self.cerrar_conexion(conexion)

		#tratamos la respuesta enviada por el servidor
		if respuesta == "NOK USER_UNKNOWN":
			return None

		respuestaParseada = respuesta.split(" ")
		user_u = user.User(respuestaParseada[2], respuestaParseada[3], respuestaParseada[4], respuestaParseada[5])

		return user_u

	#####
	# Funcion que permite listar todos los usuarios registrados en el sistema
	#
	# return : lista con los nombres de los usuarios registrados o None en caso de error
	#####
	def listar_usuarios(self):
		conexion = self.abrir_conexion()

		if conexion == None:
			return "Error de Conexion"

		#construimos la peticion de list_users y la enviamos
		peticion = "LIST_USERS"
		conexion.send(bytes(peticion, encoding = 'utf-8'))
		respuesta = conexion.recv(self.buffer).decode('utf-8')

		#tratamos la respuesta enviada por el servidor
		if respuesta == "NOK USER_UNKNOWN":
			return None

		#cogemos el numero de usuarios que nos ha devuelto el servidor
		respuesta2 = respuesta
		num_usuarios = int(respuesta2.split(" ")[2])

		num_leidos = respuesta2.count('#')
		num_usuarios -= num_leidos
		#seguimos leyendo del socket
		while num_usuarios > 0 :
			stream = conexion.recv(self.buffer).decode('utf-8')
			num_usuarios -= stream.count('#')
			respuesta += stream #concatenamos los que hemos leido

		#creamos una lista donde vamos a guardar la informacion de cada usuario
		Lista_usuarios = []

		#separamos los usuarios
		usuarios = respuesta.split("#")

		# EL primer usuario tambien tiene el OK USERS_LIST n asi que lo tratamos de forma diferente
		datos_usuario = usuarios[0].split(" ")
		user_u = user.User(datos_usuario[3], datos_usuario[4], datos_usuario[5], None)
		Lista_usuarios.append(user_u) # Cogemos el nombre del usuario

		# No incluimos el ultimo que sera un cadena vacia
		for usuario in usuarios[1:-1]:
			try:
				datos_usuario = usuario.split(" ")
				Lista_usuarios.append(user.User(datos_usuario[0], datos_usuario[1], datos_usuario[2], None))
			except IndexError:
				pass

		self.cerrar_conexion(conexion)
		return Lista_usuarios

	#####
	# Funcion que obtiene los nicks de una lista de usuarios
	# lista: lista de usuarios
	#
	# return : lista de nicks
	#####
	def parsear_usuarios(self, lista):
		nicks = []
		for user in lista:
			nicks.append(user.nick)
		return nicks


	#####
	# Funcion que permite finalizar la conexion TCP
	#
	# return : respuesta del servidor
	#####
	def cerrar_conexion(self, conexion):

		#construimos la peticion de quit y la enviamos
		peticion = "QUIT"
		conexion.send(bytes(peticion, encoding = 'utf-8'))

		respuesta = conexion.recv(self.buffer).decode('utf-8')
		conexion.close()

		return respuesta
