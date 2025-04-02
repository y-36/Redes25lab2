# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $
import socket
import os
import selectors
from base64 import b64encode
from constants import *

class Connection:
    def __init__(self, sock, directory, selector):
        self.sock = sock
        self.directory = directory
        self.selector = selector
        self.buffer = ""
        self.selector.register(sock, selectors.EVENT_READ, self.read)

    def read(self, sock):
        try:
            data = sock.recv(4096).decode("ascii")
            if not data:
                self.close()
                return
            self.buffer += data
            while EOL in self.buffer:
                line, self.buffer = self.buffer.split(EOL, 1)
                self.process_command(line.strip())
        except UnicodeDecodeError:
            self.send_error(BAD_REQUEST)
            self.close()
        except Exception as e:
            self.send_error(INTERNAL_ERROR)
            self.close()

    def process_command(self, command):
        parts = command.split()
        if not parts:
            self.send_error(INVALID_COMMAND)
            return

        cmd = parts[0]
        args = parts[1:]

        handlers = {
            "get_file_listing": self.handle_listing,
            "get_metadata": self.handle_metadata,
            "get_slice": self.handle_slice,
            "quit": self.handle_quit
        }

        handler = handlers.get(cmd, self.handle_unknown)

        if cmd == "quit":
            if len(args) != 0:
                self.send_error(INVALID_ARGUMENTS)
                return
            handler()
        elif cmd == "get_metadata":
            if len(args) != 1 or ' ' in args[0]:
                self.send_error(INVALID_ARGUMENTS)
                return
            handler(args[0])
        else:
            try:
                handler(*args)
            except TypeError:
                self.send_error(INVALID_ARGUMENTS)

    def handle_listing(self):
        try:
            files = os.listdir(self.directory)
            response = f"{CODE_OK} {error_messages[CODE_OK]}{EOL}"
            for f in files:
                response += f"{f}{EOL}"
            response += EOL
            self.send_response(response)
        except Exception:
            self.send_error(INTERNAL_ERROR)

    def handle_metadata(self, filename):
        path = os.path.join(self.directory, filename)
        if not os.path.isfile(path):
            self.send_error(FILE_NOT_FOUND)
            return
        size = os.path.getsize(path)
        self.send_response(f"{CODE_OK} {error_messages[CODE_OK]}{EOL}{size}{EOL}")

    def handle_slice(self, filename, offset_str, size_str):
        try:
            offset = int(offset_str)
            size = int(size_str)
        except ValueError:
            self.send_error(INVALID_ARGUMENTS)
            return

        path = os.path.join(self.directory, filename)
        if not os.path.isfile(path):
            self.send_error(FILE_NOT_FOUND)
            return

        file_size = os.path.getsize(path)
        if offset + size > file_size:
            self.send_error(BAD_OFFSET)
            return

        try:
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(size)
            encoded_data = b64encode(data).decode("ascii")
            self.send_response(f"{CODE_OK} {error_messages[CODE_OK]}{EOL}{encoded_data}{EOL}")
        except Exception as e:
            print(f"Error in get_slice: {e}")
            self.send_error(INTERNAL_ERROR)

    def handle_quit(self):
        self.send_response(f"{CODE_OK} {error_messages[CODE_OK]}{EOL}")
        self.close()

    def handle_unknown(self, *_):
        self.send_error(INVALID_COMMAND)

    def send_response(self, response):
        try:
            self.sock.sendall(response.encode("ascii"))
        except OSError:
            self.close()

    def send_error(self, code):
        msg = f"{code} {error_messages[code]}{EOL}"
        self.send_response(msg)
        if fatal_status(code):
            self.close()

    def close(self):
        try:
            self.selector.unregister(self.sock)
        except KeyError:
            pass
        self.sock.close()
