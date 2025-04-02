# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $
import os
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
                
    def process_command(self, command_line):
        """
        Procesa un comando recibido desde el cliente.

        Este método analiza la línea de comandos enviada por el cliente, valida 
        su estructura y ejecuta la acción correspondiente. Si el comando no es válido, 
        se envía un mensaje de error al cliente.

        Parámetros:
            command_line (str): Línea de comando enviada por el cliente.
        """
        
        # Dividir la línea de comando en partes: comando y argumentos.
        parts = command_line.split()
        if not parts:
            # Enviar un error si el comando está vacío.
            self.send_error(INVALID_COMMAND, "Empty command")
            return

        # Extraer el comando principal y sus argumentos.
        cmd = parts[0]
        args = parts[1:]

        if cmd == "quit":
            # Comando para finalizar la conexión.
            self.send_response(CODE_OK, "OK")
            self.connected = False

        elif cmd == "get_file_listing":
            # Comando para obtener la lista de archivos del directorio.
            self.handle_get_file_listing(args)

        elif cmd == "get_metadata":
            # Comando para obtener metadatos de un archivo.
            self.handle_get_metadata(args)

        elif cmd == "get_slice":
            # Comando para obtener una porción de un archivo codificada en base64.
            self.handle_get_slice(args)

        else:
            # Enviar un error si el comando es desconocido.
            self.send_error(INVALID_COMMAND, f"Unknown command: {cmd}")
    
    def handle_get_file_listing(self, args):
        """
        Genera y envía una lista de archivos en el directorio del servidor al cliente.

        Parámetros:
            args (list): Lista de argumentos recibidos del cliente. Este comando 
                         no espera argumentos adicionales, y se envía un error 
                         si se proporcionan.

        Comportamiento:
            - Si no hay argumentos, obtiene la lista de archivos en el directorio 
              configurado para el servidor.
            - La lista de archivos se envía al cliente línea por línea, terminando con '\r\n'.
            - Si ocurre un error durante la operación, se envía un mensaje de error.
        """

        # Verificar que no se reciban argumentos con este comando.
        if len(args) != 0:
            self.send_error(INVALID_ARGUMENTS, "No arguments expected")
            return

        try:
            # Obtener la lista de archivos en el directorio del servidor.
            files = os.listdir(self.directory)
            
            # Construir la respuesta con el código de éxito.
            response = f"{CODE_OK} OK{EOL}"
            for f in files:
                # Agregar cada archivo a la respuesta.
                response += f"{f}{EOL}"
            response += EOL  # Indicador de fin de lista.

            # Enviar la respuesta completa al cliente.
            self.socket.send(response.encode("ascii"))
        except Exception as e:
            # Manejar errores inesperados y enviar un mensaje al cliente.
            self.send_error(INTERNAL_ERROR, str(e))

    def handle_get_metadata(self, args):
        """
        Obtiene y envía el tamaño de un archivo en el directorio del servidor.

        Parámetros:
            args (list): Lista de argumentos recibidos del cliente. Debe contener 
                         exactamente 1 argumento: el nombre del archivo.

        Comportamiento:
            - Valida que se proporcione un único argumento, que debe ser el nombre del archivo.
            - Verifica que el archivo existe en el directorio del servidor.
            - Si el archivo es válido, se calcula su tamaño y se envía al cliente.
            - En caso de errores (archivo no encontrado, argumentos inválidos, etc.), 
            se envía un mensaje de error al cliente.
        """

        # Verificar que se proporcione exactamente un argumento: el nombre del archivo.
        if len(args) != 1:
            self.send_error(INVALID_ARGUMENTS, "Expected 1 argument: FILENAME")
            return

        # Obtener el nombre del archivo y construir la ruta completa.
        filename = args[0]
        filepath = os.path.join(self.directory, filename)

        # Verificar si el archivo existe en el directorio del servidor.
        if not os.path.isfile(filepath):
            self.send_error(FILE_NOT_FOUND, f"File '{filename}' not found")
            return

        try:
            # Obtener el tamaño del archivo en bytes.
            size = os.path.getsize(filepath)

            # Enviar respuesta exitosa al cliente con el tamaño del archivo.
            self.send_response(CODE_OK, "OK")
            self.socket.send(f"{size}{EOL}".encode("ascii"))
        except Exception as e:
            # Manejar cualquier error inesperado y enviar un mensaje de error.
            self.send_error(INTERNAL_ERROR, str(e))
            
    def handle_get_slice(self, args):
        """
        Obtiene una porción de un archivo y la envía al cliente como una cadena codificada en base64.

        Parámetros:
            args (list): Lista de argumentos proporcionados por el cliente. Deben incluir:
                         - FILENAME (str): Nombre del archivo a leer.
                         - OFFSET (int): Posición inicial en bytes dentro del archivo.
                         - SIZE (int): Cantidad de bytes a leer desde el archivo.

        Comportamiento:
            - Valida que se reciban tres argumentos: FILENAME, OFFSET y SIZE.
            - Verifica que el archivo exista en el directorio del servidor.
            - Valida que OFFSET y SIZE sean números enteros positivos y estén dentro de los 
            límites del archivo.
            - Lee la porción del archivo especificada, la codifica en base64 y la envía al cliente.
            - En caso de errores (argumentos inválidos, archivo no encontrado, etc.), 
            se envía un mensaje de error al cliente.
        """

        # Verificar que se proporcionen exactamente tres argumentos: FILENAME, OFFSET y SIZE.
        if len(args) != 3:
            self.send_error(INVALID_ARGUMENTS, "Expected 3 arguments: FILENAME OFFSET SIZE")
            return

        # Extraer argumentos y construir la ruta del archivo.
        filename, offset_str, size_str = args
        filepath = os.path.join(self.directory, filename)

        # Validar que el archivo exista en el directorio.
        if not os.path.isfile(filepath):
            self.send_error(FILE_NOT_FOUND, f"File '{filename}' not found")
            return

        # Validar que OFFSET y SIZE sean enteros positivos.
        try:
            offset = int(offset_str)
            size = int(size_str)
            if offset < 0 or size < 0:
                raise ValueError
        except ValueError:
            self.send_error(INVALID_ARGUMENTS, "Invalid OFFSET or SIZE (must be integers >= 0)")
            return

        # Validar que OFFSET + SIZE no excedan el tamaño del archivo.
        filesize = os.path.getsize(filepath)
        if offset + size > filesize:
            self.send_error(BAD_OFFSET, "OFFSET + SIZE exceeds file size")
            return

        try:
            # Leer el fragmento especificado del archivo y codificarlo en base64.
            with open(filepath, "rb") as f:
                f.seek(offset)  # Moverse al OFFSET dentro del archivo.
                fragment = f.read(size)  # Leer SIZE bytes desde OFFSET.
                encoded = base64.b64encode(fragment).decode("ascii")  # Codificar en base64.
            
            # Enviar la respuesta al cliente con el fragmento codificado.
            self.send_response(CODE_OK, "OK")
            self.socket.send(f"{encoded}{EOL}".encode("ascii"))
        except Exception as e:
            # Manejar errores inesperados y enviar un mensaje de error.
            self.send_error(INTERNAL_ERROR, str(e))
            
    


