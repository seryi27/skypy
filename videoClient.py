#####
# Redes 2
# Practica 3
# videoClient.py
#
# Carlos Hojas García-Plaza y Sergio Cordero Rojas
#
# Main del programa
#
#####


from platform import system as get_os
from src import interfaz


if __name__ == '__main__':

	interfaz_app = interfaz.interfaz("640x520")

	interfaz_app.start()
