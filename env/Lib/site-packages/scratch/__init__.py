# Copyright (c) 2012 Ben Croston
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import socket
import re
import errno
import struct

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class ScratchConnectionError(Error): pass
class ScratchNotConnected(ScratchConnectionError): pass
class ScratchConnectionRefused(ScratchConnectionError): pass
class ScratchConnectionEstablished(ScratchConnectionError): pass

class Scratch(object):
    def __init__(self, host='localhost'):
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((host, 42001))
        except socket.error as exc:
            (err, message) = exc.args
            if err == errno.EISCONN:
                raise ScratchConnectionEstablished('Already connected to Scratch')
            elif err == errno.ECONNREFUSED:
                raise ScratchConnectionRefused('Connection refused, try enabling remote sensor connections')
            else:
                print(err, message)
                raise ScratchConnectionError(message)

    def _send(self, message):
        messlen = bytearray(struct.pack('!I',len(message.encode())))
        try:
            self.connection.sendall(messlen + message.encode())
        except socket.error as exc:
            (err, message) = exc.args
            raise ScratchConnectionError(message)

    def receive(self, noparse=0):
        """Receives data from Scratch
        Arguments:
            noparse: 0 to pass message through a parser and return the message as a data structure
                     1 to not parse message, but format as a string
                     2 to not parse message and not format as a string (returns raw message)
        """
        try:
            mess = self.connection.recv(4)
            if not mess:
                return None
            (messlen,) = struct.unpack('!I',mess)
            messlen += 4
            while len(mess) < messlen:
                mess += self.connection.recv(messlen-len(mess))
        except socket.error as exc:
            (errno, message) = exc.args
            raise ScratchConnectionError(errno, message)
        if not mess:
            return None
        if noparse == 0:
            return self._parse_message(repr(mess))
        if noparse == 1:
            return repr(mess)
        elif noparse == 2:
            return mess
        else:
            return self._parse_message(repr(mess))

    def sensorupdate(self, data):
        """Takes a dictionary and writes a message using the keys as sensors, and the values as the update values"""
        if not isinstance(data, dict):
            raise TypeError('Expected a dict')
        message = 'sensor-update'
        for k,v in data.items():
            message += ' "%s" %s'%(k, v)
        self._send(message)

    def broadcast(self, data):
        """Takes a list of message strings and writes a broadcast message to scratch"""
        if isinstance(data, list):
            message = 'broadcast'
            for mess in data:
                message += ' "%s"'%mess
            self._send(message)
        else:
            self._send('broadcast "%s"'%data)

    def _parse_message(self, message):
        #TODO: parse sensorupdates with quotes in sensor names and values
        #      make more readable
        if message:
            sensorupdate_re = 'sensor-update[ ](((?:\").[^\"]*(?:\"))[ ](?:\"|)(.[^\"]*)(?:\"|)[ ])+'
            broadcast_re = 'broadcast[ ]\".[^"]*\"'
            sensors = {}
            broadcast = []

            sensorupdates = re.search(sensorupdate_re, message)
            if sensorupdates:
                # formats string to '<sensor> <value> <sensor1> <value1> ...'
                sensorupdates = sensorupdates.group().replace('sensor-update', '').strip().split()
                # for sensors that are multiple words, make sure that entire sensor name
                # shows up as one sensor value in the list
                i = 0
                sensorlist = []
                while i < len(sensorupdates):
                    if sensorupdates[i][0] == '\"':
                        if sensorupdates[i][-1] != '\"':
                            j = i
                            multisense = ''
                            #now loop through each word in list and find the word
                            #that ends with " which is the end of the variable name
                            while j < len(sensorupdates):
                                multisense = multisense+' '+sensorupdates[j]
                                if sensorupdates[j][-1] == '\"':
                                    break
                                i+=1
                                j+=1
                            sensorlist.append(multisense.strip(' \"'))
                        else:
                            sensorlist.append(sensorupdates[i].strip(' \"'))
                    else:
                        sensorlist.append(sensorupdates[i])
                    i+=1
                i = 0
                # place sensor name and values in a dictionary
                while len(sensors) < len(sensorlist)/2:
                    sensors[sensorlist[i]] = sensorlist[i+1]
                    i+=2

            broadcasts = re.findall(broadcast_re, message)
            if broadcasts:
                # strip each broadcast message of quotes ("") and "broadcast"
                broadcast = [mess.replace('broadcast','').strip('\" ') for mess in broadcasts]

            return dict([('sensor-update', sensors), ('broadcast', broadcast)])
        else:
            return None
