# -*- coding: utf-8 -*-
"""
A short example that demonstrates a client that makes HEAD requests to certain
websites.

This example is intended as a reproduction of nghttp2 issue 396, for the
purposes of compatibility testing.
"""
from __future__ import print_function

from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded,
    StreamReset, SettingsAcknowledged,
)
from hyperframe.frame import SettingsFrame

from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import connectProtocol, SSL4ClientEndpoint

import shared

PATH = '/'

class H2Protocol(Protocol):
    def __init__(self):
        self.conn = H2Connection()
        self.known_proto = None
        self.request_made = False

    def connectionMade(self):
        print (f'Connected to server running on' + \
            f'{shared.AUTHORITY}:{str(shared.PORT)}')
        self.conn.initiate_connection()
        # This reproduces the error in #396,
        # by changing the header table size.
        self.conn.update_settings(
            {
                SettingsFrame.HEADER_TABLE_SIZE: shared.SIZE
            })
        
        self.transport.write(self.conn.data_to_send())


    def dataReceived(self, data):
        print('I received some data')
        if not self.known_proto:
            self.known_proto = self.transport.negotiatedProtocol
            assert self.known_proto == b'h2'

        events = self.conn.receive_data(data)

        for event in events:
            print(type(event))
            
            if isinstance(event, ResponseReceived):
                self.handleResponse(event.headers, event.stream_id)
            elif isinstance(event, DataReceived):
                self.handleData(event.data, event.stream_id)
            elif isinstance(event, StreamEnded):
                self.endStream(event.stream_id)
            elif isinstance(event, SettingsAcknowledged):
                self.settingsAcked(event)
            elif isinstance(event, StreamReset):
                reactor.stop()
                raise RuntimeError("Stream reset: %d" % event.error_code)
            else:
                print(event)

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def settingsAcked(self, event):
        print('Settings successfully acked')
        # Having received the remote settings change, lets send our request.
        if not self.request_made:
            self.sendRequest()

    def handleResponse(self, response_headers, stream_id):
        for name, value in response_headers:
            print("%s: %s" % (name.decode("utf-8"), value.decode("utf-8")))

        print("")

    def handleData(self, data, stream_id):
        print(data.decode("utf-8"), end='')
        print('')

        
    def endStream(self, stream_id):
        print('Ending the stream')
        self.conn.close_connection()
        self.transport.write(self.conn.data_to_send())
        self.transport.loseConnection()
        reactor.stop()

    def sendRequest(self):
        request_headers = [
            (':method', 'HEAD'),
            (':authority', shared.AUTHORITY),
            (':scheme', 'https'),
            (':path', PATH),
            ('user-agent', 'hyper-h2/1.0.0'),
        ]
        self.conn.send_headers(1, request_headers, end_stream=True)
        self.request_made = True

tls_options = shared.compute_tls_options()

connectProtocol(
    SSL4ClientEndpoint(
        reactor, shared.AUTHORITY, shared.PORT, tls_options
    ),
    H2Protocol()
)

reactor.run()

