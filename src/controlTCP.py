#####
# Redes 2
# Practica 3
# controlTCP.py
#
# Carlos Hojas García-Plaza y Sergio Cordero Rojas
#
# Se encuentran todas las funciones que se encarga del envio y recpecion TCP
#
#####

import socket

class controlTCP:

    #####
	# En esta clase vamos a realizar las funciones relacionadas con el control de la conexion TCP con el nodo destino
	#####


    #socket de envio de peticiones
    socket_conexion = None

    #socket de recepcion de peticiones
    socket_recepcion = None

    #puerto donde recibimos las comunicaciones TCP
    puerto_origen_TCP = None

    #puerto donde recibimos las comunicaciones TCP
    puerto_origen_UDP = None

    #IP del usuario
    IP_origen = None

    #tamaño maximo de peticiones en espera
    tam_max_pet = 8



    #####
	# Constructor de la clase
    #
	#####
    def __init__(self, puerto_origen_UDP, puerto_origen_TCP, IP_origen):
        self.puerto_origen_TCP = puerto_origen_TCP
        self.puerto_origen_UDP = puerto_origen_UDP
        self.IP_origen = IP_origen

        #Construimos el socket para recibir peticiones
        self.socket_recepcion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_recepcion.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_recepcion.bind(("0.0.0.0", int(self.puerto_origen_TCP)))
        self.socket_recepcion.listen(self.tam_max_pet)



    ###########################################################################################################
    ############################   Funciones de envio de peticiones ###########################################
    ###########################################################################################################


    #####
	# Funcion que se encarga de enviar una peticion a una IP y un pueto determinados
    #
    # peticion: peticion a enviar
    #
	# return : OK si es enviada correctamente,
    #          None en caso de socket vacio,
    #          Aborted en caso de la conexion haya sido cerrada por algun error
	#####
    def enviar_peticion(self, peticion):
        if self.socket_conexion == None:
            print("Error en enviar peticion: socket vacio")
            return None

        #enviamos la peticion
        print(peticion)
        try:
            self.socket_conexion.send(bytes(peticion, encoding = 'ASCII'))
        except (ConnectionError, OSError):
            return "Aborted"
        return "OK"


    #####
	# Funcion que se encarga de señalizar que un nodo quiere establecer una videollamada con otro
    #
    # usuario: nuestro nombre de usuario
    #
	# return : None en caso de error, OK en caso de acierto
	#####
    def calling(self, usuario):
        # construimos la peticion de calling y la enviamos
        peticion = "CALLING {} {}".format(usuario, self.puerto_origen_UDP)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"


    #####
	# Funcion que se encarga de señalizar que se desea pausar temporalmente una llamada, sin cortarla
    #
	# usuario: nuestro nombre de usuario
    #
	# return : None en caso de error, OK en caso de acierto
	#####
    def hold(self, usuario):
        if self.socket_conexion == None:
            print("Error en tcp_hold: socket de conexion vacio")
            return None

        # construimos la peticion de hold y la enviamos
        peticion = "CALL_HOLD {}".format(usuario)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"


    #####
	# Funcion que se encarga de señalizar que se desea reanudar una llamada anteriormente pausada
    #
	# usuario: nuestro nombre de usuario
    #
	# return : None en caso de error, OK en caso de acierto
	#####
    def resume(self, usuario):
        if self.socket_conexion == None:
            print("Error en tcp_resume: socket de conexion vacio")
            return None

        # construimos la peticion de resume y la enviamos
        peticion = "CALL_RESUME {}".format(usuario)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"


    #####
	# Funcion que se encarga de señalizar que se desea finalizar una llamada
    #
    # usuario: nuestro nombre de usuario
    #
	# return : None en caso de error, OK en caso de acierto
	#####
    def end(self, usuario):
        if self.socket_conexion == None:
            print("Error en tcp_quit: socket de conexion vacio")
            return None

        # construimos la peticion de end y la enviamos
        peticion = "CALL_END {}".format(usuario)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"

    ###########################################################################################################
    ############################   Funciones de respuesta a CALLING ###########################################
    ###########################################################################################################

    #####
	# Funcion que se encarga de enviar una respuesta CALL_ACCEPTED despues de un recibir un calling
    #
    # usuario: nombre del usuario
    #
	# return : None en caso de error
	#####
    def call_accepted(self, usuario):
		# construimos la respuesta al CALLING y la enviamos
        peticion = "CALL_ACCEPTED {} {}".format(usuario, self.puerto_origen_UDP)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"

    #####
	# Funcion que se encarga de enviar una respuesta CALL_DENIED despues de un recibir un calling
    #
    # usuario: nuestro nombre del usuario
    #
	# return : None en caso de error, OK en caso de acierto
	#####
    def call_denied(self, usuario):
		# construimos la respuesta al CALLING y la enviamos
        peticion = "CALL_DENIED {}".format(usuario)
        control = self.enviar_peticion(peticion)
        if control == None:
            return None
        return "OK"

    #####
	# Funcion que se encarga de enviar una respuesta CALL_BUSY despues de un recibir un calling
    #
    # socket: socket de conexion, en este caso tenemos que pasarlo como argumento porque no vamos a guardar el socket
    #       puesto que no establecemos conexion
    #
	#####
    def call_busy(self, socket):
		#c onstruimos la respuesta al CALLING y la enviamos
        peticion = "CALL_BUSY"
        print(peticion)
        socket.send(bytes(peticion, encoding = 'ASCII'))
        socket.close()
