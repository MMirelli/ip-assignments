from __future__ import print_function

import time
from collections import OrderedDict

from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded,
    StreamReset, SettingsAcknowledged,
    PushedStreamReceived)
from twisted.internet import defer, error
from twisted.internet import reactor, task
from twisted.internet.endpoints import connectProtocol, SSL4ClientEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import optionsForClientTLS, Certificate

import shared


class H2Protocol(Protocol):

    def __init__(self):
        self.conn = H2Connection()
        self.known_proto = None
        self.sent_request = 0
        # paths to use for the initial GET requests
        self.paths = ['push/espoo/helsinki', 'push/helsinki']
        self.promised_streams = {}
        self.client_cache = {}

    def connectionMade(self):
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def dataReceived(self, data):
        if not self.known_proto:
            self.known_proto = self.transport.negotiatedProtocol
            assert self.known_proto == b'h2'

        events = self.conn.receive_data(data)

        for event in events:
            print("")
            print(type(event))
            if isinstance(event, ResponseReceived):
                self.handleResponse(event.headers, event.stream_id)
            elif isinstance(event, DataReceived):
                self.handleData(event.data, event.stream_id)
            elif isinstance(event, PushedStreamReceived):
                self.handlePushPromise(event.headers, event.pushed_stream_id)
            elif isinstance(event, StreamEnded):
                self.terminateRequest(event.stream_id)
            elif isinstance(event, SettingsAcknowledged):
                self.settingsAcked(event)
            elif isinstance(event, StreamReset):
                reactor.stop()
                raise RuntimeError("Stream reset: %d" % event.error_code)
            else:
                print("Unhandled event: ", type(event))

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def settingsAcked(self, event):
        # This prevents sending more requests than number of paths in
        # in self.paths.
        if self.sent_request < len(self.paths):
            interval = 10
            # starts async calls of sendRequest, executed after interval 
            # (sec) elapses
            repeating = task.LoopingCall(self.sendRequest)
            repeating.start(interval, now=True)

    def handlePushPromise(self, promised_headers, push_stream_id):
        # Save the ID and resource address of the promised push stream for checking later incoming streams
        promised_headers = OrderedDict(promised_headers)
        print('Stream #', push_stream_id, ' will deliver data from: ',
              promised_headers[b':path'].decode("utf-8"))
        self.promised_streams[push_stream_id] = promised_headers[b':path'].decode("utf-8")

    def handleResponse(self, response_headers, stream_id):
        # Check if the frame came from a push stream
        if stream_id in self.promised_streams.keys():
            print("handling HEADERS of push silently")
            return

        # Handle normally
        for name, value in response_headers:
            print("%s: %s" % (name.decode("utf-8"), value.decode("utf-8")))

    def handleData(self, data, stream_id):
        # Check if the frame came from a push stream
        if stream_id in self.promised_streams.keys():
            # Cache the pushed data with the resource path
            self.client_cache[self.promised_streams[stream_id]] = data
            print("handling DATA of push silently")
            return

        # Handle normally
        print(data.decode("utf-8"), end='')

    def terminateRequest(self, stream_id):
        '''
        Terminates request 
        
        N.B. the stream is terminated by the sendRequest 
             send_headers function call
        '''

        # if stream_id not in self.promised_streams.keys():
        #     self.sent_request += 1

        if self.sent_request == len(self.paths):
            self.terminateConnection()

    def terminateConnection(self):
        '''
        Ends connection, note that streams are endend by send_headers
        in sendRequest.
        '''
        # this closes the HTTP/2 connection 
        self.conn.close_connection()
        # terminates HTTP connection
        # this closes the tcp connection
        self.transport.write(self.conn.data_to_send())
        # stops the client
        self.transport.loseConnection()
        reactor.stop()

    def sendRequest(self):

        # Check if the data for this request path has already been cached
        if self.paths[self.sent_request] in self.client_cache:
            print("")
            print("GET request for " + self.paths[self.sent_request])
            print("Fetching data from cache")
            cached_data = self.client_cache[self.paths[self.sent_request]]
            print(cached_data.decode("utf-8"), end='')
            self.sent_request += 1
            # Check if we need to terminate the client
            self.terminateRequest(999)
            return

        request_headers = [
            (':method', 'GET'),
            (':authority', shared.AUTHORITY),
            (':scheme', 'https'),
            (':path', self.paths[self.sent_request]),
            ('user-agent', 'hyper-h2/1.0.0'),
        ]
        stream_id = self.conn.get_next_available_stream_id()
        print(f"Sending request using stream {stream_id}")
        # send application layer HTTP/2 request and ends the current stream
        self.conn.send_headers(stream_id, request_headers,
                               end_stream=True)

        # send transport layer TCP request (using Twisted)
        self.transport.write(self.conn.data_to_send())

        self.sent_request += 1


# NOT USED, it might be deleted
class ShowCertificate(Protocol):
    def connectionMade(self):
        self.transport.write(b"GET / HTTP/1.0\r\n\r\n")
        self.done = defer.Deferred()

    def dataReceived(self, data):
        certificate = Certificate(self.transport.getPeerCertificate())
        print("OK:", certificate)
        self.transport.abortConnection()

    def connectionLost(self, reason):
        print("Lost.")
        if not reason.check(error.ConnectionClosed):
            print("BAD:", reason.value)
        self.done.callback(None)


tls_options = shared.compute_tls_options()

connectProtocol(
    SSL4ClientEndpoint(reactor, shared.AUTHORITY, 8822, tls_options),
    # ShowCertificate(),
    H2Protocol(),
)

reactor.run()
