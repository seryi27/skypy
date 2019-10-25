class User:

	def __init__(self, nick, IP, puerto, versiones):
		self.nick = nick
		self.IP = IP
		self.puerto = puerto
		self.versiones = versiones

	def __str__(self):
		return "nick: " + self.nick + "\nIP: " + self.puerto + "\nPuerto: " + self.puerto + "\nVersiones:" + self.versiones + "\n\n"
