# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $

import socket
from constants import *
from base64 import b64encode

class Connection(object):
    """
    Conexión punto a punto entre el servidor y un cliente.
    Se encarga de satisfacer los pedidos del cliente hasta
    que termina la conexión.
    """

    def __init__(self, socket, directory):
        self.socket = socket
        self.directory = directory
        self.connected = True

    def handle(self):
        """
        Atiende eventos de la conexión mientras esta permanece activa.

        El método recibe datos del socket del cliente, valida el formato, 
        y procesa los comandos enviados. Si ocurre un error o el cliente 
        cierra la conexión, se finaliza el manejo de la conexión.
        """
   
        while self.connected:
            try:
                # Recibir datos del socket con un tamaño máximo de 1024 bytes.
                data = self.socket.recv(1024).decode("ascii")
                if not data:
                    # Si no se recibe ningún dato, el cliente cerró la conexión.
                    break  # Cliente cerró la conexión

                # Validar terminador \r\n
                if EOL not in data:
                    self.send_error(BAD_EOL, "Missing EOL")
                    # Finalizar conexión si el terminador no es válido.
                    self.connected = False
                    break
                # Extraer y limpiar la línea de comandos enviada por el cliente.
                command_line = data.split(EOL)[0].strip()
                # Procesar el comando recibido.
                self.process_command(command_line)
                
            except Exception as e:
                self.send_error(INTERNAL_ERROR, str(e))
                self.connected = False
