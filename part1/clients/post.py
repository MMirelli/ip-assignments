# -*- coding: utf-8 -*-
"""
A short example that demonstrates a client that makes POST requests to certain
websites.
This example is intended to demonstrate how to handle uploading request bodies.
In this instance, a file will be uploaded. In order to handle arbitrary files,
this example also demonstrates how to obey HTTP/2 flow control rules.
Takes one command-line argument: a path to a file in the filesystem to upload.
If none is present, uploads this file.
"""
from __future__ import print_function

import mimetypes
import os
import sys
import json
import glob
import re
import argparse

from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded, StreamReset, WindowUpdated,
    SettingsAcknowledged,
)
from twisted.internet import reactor, defer, task
from twisted.internet.endpoints import connectProtocol, SSL4ClientEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import optionsForClientTLS

import shared

parser = argparse.ArgumentParser()
parser.add_argument('--method', default='POST',
                    help='Select a method. By default POST.',
                    choices=['POST', 'PUT']
)

STATIC_FILES_PATH = os.path.join('..', 'static')
parser.add_argument('--static', default=STATIC_FILES_PATH,
                    help='Enter the folder where client\'s data is.',
)

parser.add_argument('--just_one', default=False, type=bool,
                    help='Set to True to send only the first image.',
)

IMAGES_PATH = 'images'
parser.add_argument('--images', default=IMAGES_PATH,
                    help='Enter the folder where client\'s images are.',
)

args = parser.parse_args()

METADATA_FILE = 'metadata.json' 

class H2Protocol(Protocol):
    def __init__(self, method):
        self.conn = H2Connection()
        self.known_proto = None
        self.flow_control_deferred = None
        self.fileobj = None
        self.file_sizes = []
        self.sent_request = 0
        self.coordinates = self.extract_coordinates() 
        self.image_names = self.get_image_names()
        self.method = method

        print(self.image_names)
        
        print(f"Starting the {self.method} client")

    def connectionMade(self):
        """
        Called by Twisted when the TCP connection is established. We can start
        sending some data now: we should open with the connection preamble.
        """

        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def dataReceived(self, data):
        """
        Called by Twisted when data is received on the connection.
        We need to check a few things here. Firstly, we want to validate that
        we actually negotiated HTTP/2: if we didn't, we shouldn't proceed!
        Then, we want to pass the data to the protocol stack and check what
        events occurred.
        """
        if not self.known_proto:
            self.known_proto = self.transport.negotiatedProtocol
            assert self.known_proto == b'h2'

        events = self.conn.receive_data(data)

        for event in events:
            print(event)
            if isinstance(event, ResponseReceived):
                self.handleResponse(event.headers)
            elif isinstance(event, DataReceived):
                self.handleData(event.data)
            elif isinstance(event, StreamEnded):
                self.connectionLost()
            elif isinstance(event, SettingsAcknowledged):
                self.settingsAcked(event)
            elif isinstance(event, StreamReset):
                reactor.stop()
                raise RuntimeError("Stream reset: %d" % event.error_code)
            elif isinstance(event, WindowUpdated):
                self.windowUpdated(event)

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def settingsAcked(self, event):
        """
        Called when the remote party ACKs our settings. We send a SETTINGS
        frame as part of the preamble, so if we want to be very polite we can
        wait until the ACK for that frame comes before we start sending our
        request.
        """
        if self.sent_request < len(self.coordinates):
            interval = 1
            # starts async calls of sendRequest, executed after interval 
            repeating = task.LoopingCall(self.sendRequest)
            repeating.start(interval, now=True)
            
    def handleResponse(self, response_headers):
        """
        Handle the response by printing the response headers.
        """
        for name, value in response_headers:
            print("%s: %s" % (name, value))

        print("")

    def handleData(self, data):
        """
        We handle data that's received by just printing it.
        """
        print(data, end='')

    def endStream(self):
        """
        We call this when the stream is cleanly ended by the remote peer. That
        means that the response is complete.
        Because this code only makes a single HTTP/2 request, once we receive
        the complete response we can safely tear the connection down and stop
        the reactor. We do that as cleanly as possible.
        """
        self.conn.close_connection()
        # stops TCP connection
        self.transport.write(self.conn.data_to_send())
        self.transport.loseConnection()

    def windowUpdated(self, event):
        """
        We call this when the flow control window for the connection or the
        stream has been widened. If there's a flow control deferred present
        (that is, if we're blocked behind the flow control), we fire it.
        Otherwise, we do nothing.
        """
        if self.flow_control_deferred is None:
            return

        # Make sure we remove the flow control deferred to avoid firing it
        # more than once.
        flow_control_deferred = self.flow_control_deferred
        self.flow_control_deferred = None
        flow_control_deferred.callback(None)

    def terminateConnection(self):
        """
        Gracefully stops the connection to the server.
        """
        # closes the file
        if self.fileobj is not None:
            self.fileobj.close()
        # closes the HTTP connection
        self.conn.close_connection()
        # this closes the tcp connection
        self.transport.loseConnection()
        print("Terminating the client")
        if reactor.running:
            # stops the client
            reactor.stop()

        
    def connectionLost(self, reason=None):
        """
        Terminates the connection only after all the coordinates 
        have been processed.
        """
        if reason is not None or \
           self.sent_request >= len(self.coordinates):

            self.terminateConnection()
        
    def file_exists(self, image_path):
        if os.path.isfile(image_path):
            print (f"File {image_path} found, forwarding it to",\
                f"the server running on {shared.get_host()}")
            return True
        else:
            print (f"File {image_path} not found.")
            self.endStream()
            self.connectionLost("File not found")
            return False

    def current_image_path(self):
        print(self.current_request_n())
        return self.image_names[self.current_request_n()]

    def current_request_n(self):
        return 0 if args.just_one else self.sent_request 
    
    def sendRequest(self):
        """
        Send the POST request.
        A POST request is made up of one headers frame, and then 0+ data
        frames. This method begins by sending the headers, and then starts a
        series of calls to send data.
        """
        image_path = self.current_image_path()

        if not self.file_exists(image_path):
            return
        # First, we need to work out how large the file is.
        self.file_sizes.append(os.stat(image_path).st_size)

        # Next, we want to guess a content-type and content-encoding.
        content_type, content_encoding = \
            mimetypes.guess_type(image_path)
        
        cur_request_n = self.current_request_n()
        
        cur_coord = self.coord2String(self.coordinates[cur_request_n])
        request_path = os.path.join(self.method2path(),
                                    str(cur_request_n) +'-' + cur_coord)
        # Now we can build a header block.
        request_headers = [
            (':method', self.method),
            (':authority', shared.AUTHORITY),
            (':scheme', 'https'),
            (':path', request_path),
            ('user-agent', 'hyper-h2/1.0.0'),
            ('content-length', str(self.current_file_size(self.sent_request))),
        ]

        # adding extra headers
        if content_type is not None:
            request_headers. \
                append(('content-type', content_type))

            if content_encoding is not None:
                request_headers. \
                    append(
                        ('content-encoding', content_encoding)
                    )
                
        stream_id = self.conn.get_next_available_stream_id()
        # sending the header frame
        self.conn.send_headers(stream_id, request_headers)

        # We can now open the file.
        self.fileobj = open(image_path, 'rb')

        # We now need to send all the relevant data. We do this by checking
        # what the acceptable amount of data is to send, and sending it. If we
        # find ourselves blocked behind flow control, we then place a deferred
        # and wait until that deferred fires.
        self.sendFileData(None, stream_id, self.sent_request)
        self.sent_request += 1

    def current_file_size(self, req_number):
        return self.file_sizes[req_number]
        
    def sendFileData(self, previous_rst, stream_id, req_number):
        """
        Send some file data on the connectioon, using h2 default flow control.
        """
        # Firstly, check what the flow control window is for stream 1.
        window_size = self.conn.\
            local_flow_control_window(stream_id)

        # Next, check what the maximum frame size is.
        max_frame_size = self.conn.max_outbound_frame_size

        print( 'Spare bytes to send per file:\n ' +
               ','.join([str(fs) for fs in self.file_sizes]))
        
        print(f"Number of images sent: {len(self.file_sizes)}")

        # We will send no more than the window size or the remaining file size
        # of data in this call, whichever is smaller.
        bytes_to_send = min(window_size, self.current_file_size(req_number))
        print(f'Bytes to be sent: {bytes_to_send}')
        # We now need to send a number of data frames.

        while bytes_to_send > 0:
            chunk_size = min(bytes_to_send, max_frame_size)
            data_chunk = self.fileobj.read(chunk_size)
            self.conn.send_data(stream_id=stream_id, data=data_chunk)

            bytes_to_send -= chunk_size
            
            self.file_sizes[req_number] = \
                self.current_file_size(req_number) - chunk_size

        # We've prepared a whole chunk of data to send. If the file is fully
        # sent, we also want to end the stream: we're done here.
        if self.current_file_size(req_number) == 0:
            self.conn.end_stream(stream_id)
        else:
            # We've still got data left to send but the window is closed. Save
            # a Deferred that will call us when the window gets opened.
            self.flow_control_deferred = defer.Deferred()
            self.flow_control_deferred.addCallback(
                self.sendFileData, stream_id, req_number
            )
            
        print(self.conn.open_outbound_streams)
        self.transport.write(self.conn.data_to_send())

#########extra_utilities################################

    def atoi(self, text):
        
        return int(text) if text.isdigit() else text

    def natural_keys(self, text):
        '''
        alist.sort(key=natural_keys) sorts in human order
        http://nedbatchelder.com/blog/200712/human_sorting.html
        '''
        return [ self.atoi(c) for c in re.split(r'(\d+)', text) ]

    def get_image_names(self):
        '''
        Gets the image names, sorting them by the number contained in their
        title.
        '''
        images_re = os.path.join(args.images, 'gsv_*.jpg')
        image_names = glob.glob(images_re)
        image_names.sort(key=self.natural_keys)
        return image_names

    def coord2String (self, coordinations):
        return ','.join([str(v) for v in coordinations]).replace('.','_')

    def extract_coordinates(self):
        '''
        It extracts all coordinates in metadata.json.
        '''

        fileFullname = os.path.join(
            args.static, METADATA_FILE
        )
        with open(fileFullname) as json_file:
            parsed = json.load(json_file)

        return parsed['route']


    def fetch_image(self, image_name):
        '''
        Fetches an image from the client.
        '''
        imageFullname = os.path.join(
            IMAGES_PATH, image_name
        )
        with open(imageFullname,'rb') as imageFile:
            imageBytes = imageFile.read()
        return imageBytes

    def method2path(self):
        return '/' + self.method.lower()
    
options = shared.compute_tls_options()

connectProtocol(
    SSL4ClientEndpoint(reactor, shared.AUTHORITY,
                       shared.PORT, options),
    H2Protocol(args.method)
)

reactor.run()
