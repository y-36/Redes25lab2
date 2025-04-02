#!/usr/bin/env python
# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Revisión 2014 Carlos Bederián
# Revisión 2011 Nicolás Wolovick
# Copyright 2008-2010 Natalia Bidart y Daniel Moisset
# $Id: server.py 656 2013-03-18 23:49:11Z bc $
import optparse
import socket
import selectors
import os
import sys
from connection import Connection
from constants import *

class Server(object):
    def __init__(self, addr=DEFAULT_ADDR, port=DEFAULT_PORT, directory=DEFAULT_DIR):
        # Crear directorio si no existe
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        self.directory = os.path.abspath(directory)  # Ruta absoluta para evitar errores

        # Configurar socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((addr, port))
        except PermissionError as e:
            sys.stderr.write(f"Error: Permisos insuficientes para el puerto {port}.\n")
            sys.exit(1)
        self.sock.listen(5)
        self.sock.setblocking(False)

        # Configurar selector para múltiples clientes
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.sock, selectors.EVENT_READ, self.accept)

        print(f"Serving {self.directory} on {addr}:{port}.")

    def accept(self, sock):
        """Acepta una nueva conexión y registra su socket en el selector."""
        try:
            conn, addr = sock.accept()
            conn.setblocking(False)
            Connection(conn, self.directory, self.selector)
            print(f"Connected by: {addr}")
        except socket.error as e:
            print(f"Error accepting connection: {e}")

    def serve(self):
        """Bucle principal del servidor."""
        try:
            while True:
                events = self.selector.select(timeout=1)  # Timeout para evitar bloqueo
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj)
        except KeyboardInterrupt:
            print("\nServer shutting down gracefully.")
        except Exception as e:
            print(f"Critical error: {e}")
        finally:
            self.selector.close()
            self.sock.close()
            print("Server stopped.")

def main():
    parser = optparse.OptionParser()
    parser.add_option("-p", "--port", type="int", default=DEFAULT_PORT,
                      help="Número de puerto TCP donde escuchar")
    parser.add_option("-a", "--address", default=DEFAULT_ADDR,
                      help="Dirección donde escuchar")
    parser.add_option("-d", "--datadir", default=DEFAULT_DIR,
                      help="Directorio compartido")

    options, args = parser.parse_args()
    if len(args) > 0:
        parser.print_help()
        sys.exit(1)

    # Validar puerto
    if not (0 < options.port <= 65535):
        sys.stderr.write(f"Puerto inválido: {options.port}. Debe ser 1-65535.\n")
        sys.exit(1)

    try:
        server = Server(options.address, options.port, options.datadir)
        server.serve()
    except Exception as e:
        sys.stderr.write(f"Error al iniciar el servidor: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
