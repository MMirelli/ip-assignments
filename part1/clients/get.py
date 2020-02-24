from __future__ import print_function

import shared
from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded,
    StreamReset, SettingsAcknowledged,
)
from twisted.internet import defer, error
from twisted.internet import reactor, task
from twisted.internet.endpoints import connectProtocol, SSL4ClientEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import Certificate


class H2Protocol(Protocol):

    def __init__(self):
        self.conn = H2Connection()
        self.known_proto = None
        self.sent_request = 0
        # paths to use for the initial GET requests
        self.paths = ['get/[60.18306549999999, 24.831656399999996]', 'get/[60.170164699999994, 24.9393885]']

    def connectionMade(self):
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def dataReceived(self, data):
        if not self.known_proto:
            self.known_proto = self.transport.negotiatedProtocol
            assert self.known_proto == b'h2'

        events = self.conn.receive_data(data)

        for event in events:
            print(type(event))
            print("")
            if isinstance(event, ResponseReceived):
                self.handleResponse(event.headers, event.stream_id)
            elif isinstance(event, DataReceived):
                self.handleData(event.data, event.stream_id)
            elif isinstance(event, StreamEnded):
                self.terminateRequest(event.stream_id)
            elif isinstance(event, SettingsAcknowledged):
                self.settingsAcked(event)
            elif isinstance(event, StreamReset):
                reactor.stop()
                raise RuntimeError("Stream reset: %d" % event.error_code)
            else:
                print("Unhandled event: ", type(event))
                print("")

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def settingsAcked(self, event):
        # This prevents sending more requests than number of paths in
        # in self.paths.
        if self.sent_request < len(self.paths):
            interval = 2
            # starts async calls of sendRequest, executed after interval 
            # (sec) elapses
            repeating = task.LoopingCall(self.sendRequest)
            repeating.start(interval, now=True)

    def handleResponse(self, response_headers, stream_id):
        for name, value in response_headers:
            print("%s: %s" % (name.decode("utf-8"), value.decode("utf-8")))
        print("")

    def handleData(self, data, stream_id):
        print(data.decode("utf-8"), end='')
        print("")

    def terminateRequest(self, stream_id):
        '''
        Terminates request 
        
        N.B. the stream is terminated by the sendRequest 
             send_headers function call
        '''
        self.sent_request += 1

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
