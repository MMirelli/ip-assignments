# -*- coding: utf-8 -*-
"""
asyncio-server.py
~~~~~~~~~~~~~~~~~
A fully-functional HTTP/2 server using asyncio. Requires Python 3.5+.
This example demonstrates handling requests with bodies, as well as handling
those without. In particular, it demonstrates the fact that DataReceived may
be called multiple times, and that applications must handle that possibility.
"""
import asyncio
import collections
import json
import os
import ssl
import time
from collections import OrderedDict
from typing import List, Tuple
from PIL import Image
import types

import sslkeylog
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.errors import ErrorCodes
from h2.events import (
    ConnectionTerminated, DataReceived, RemoteSettingsChanged,
    RequestReceived, StreamEnded, StreamReset, WindowUpdated
)
from h2.exceptions import ProtocolError, StreamClosedError
from h2.settings import SettingCodes

import io
import os
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('--show', default=False,
                    help='Set True to show images sent by the client.',
)

args = parser.parse_args()

SERVER_NAME = 'asyncio-h2'
STATIC_FOLDER = 'static'
METADATA = 'static/metadata.json'
SERVER_STORAGE = 'server_storage'

RequestData = collections.namedtuple('RequestData', ['headers', 'data'])

class H2Protocol(asyncio.Protocol):
    def __init__(self):
        config = H2Configuration(client_side=False, header_encoding='utf-8')
        self.conn = H2Connection(config=config)
        self.transport = None
        self.stream_data = {}
        self.flow_control_futures = {}
        self.received_images_c = 0

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def connection_lost(self, exc):
        for future in self.flow_control_futures.values():
            future.cancel()
        self.flow_control_futures = {}

    def data_received(self, data: bytes):
        try:
            events = self.conn.receive_data(data)
        except ProtocolError as e:
            print(e)
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
        else:
            self.transport.write(self.conn.data_to_send())
            for event in events:
                print("")
                print(type(event))
                if isinstance(event, RequestReceived):
                    self.request_received(event.headers, event.stream_id)
                elif isinstance(event, DataReceived):
                    self.receive_data(event.data, event.stream_id)
                elif isinstance(event, StreamEnded):
                    self.stream_complete(event.stream_id)
                elif isinstance(event, ConnectionTerminated):
                    self.transport.close()
                elif isinstance(event, StreamReset):
                    self.stream_reset(event.stream_id)
                elif isinstance(event, WindowUpdated):
                    self.window_updated(event.stream_id, event.delta)
                elif isinstance(event, RemoteSettingsChanged):
                    if SettingCodes.INITIAL_WINDOW_SIZE in event.changed_settings:
                        self.window_updated(None, 0)
                self.transport.write(self.conn.data_to_send())

    def request_received(self, headers: List[Tuple[str, str]], stream_id: int):
        headers = OrderedDict(headers)
        method = headers[':method']
        path_variables = headers[':path'].split('/')

        print('got a %s request' % method)
        # We only support GET, POST and PUT .
        if method not in ('GET', 'POST', 'PUT'):
            self.send_response_headers(statusCode=405, stream_id=stream_id)
            return

        # TODO: check diffs for conflicts with master and confirm messages with wireshark

        # Check if request is GET and supports push
        if (method == 'GET') & (path_variables[0] == 'push'):
            path = path_variables[1] + ".json"  # e.g. "espoo"
            full_path = os.path.join(STATIC_FOLDER, path)
            print(full_path)
            if not os.path.exists(full_path):
                # Invalid path respond with a 404
                response_headers = (
                    (':status', '404'),
                    ('content-length', '0'),
                    ('server', 'asyncio-h2'),
                )
                self.conn.send_headers(
                    stream_id, response_headers, end_stream=True
                )
                self.transport.write(self.conn.data_to_send())
                return
            else:
                # Valid path, save the paths to stream_data for processing and sending a response
                self.stream_data[stream_id] = path_variables
                return

        if (method == 'GET') & (path_variables[0] == 'get'):
            self.stream_data[stream_id] = path_variables

        elif (method == 'POST') or (method == 'PUT'):
            # Store off the request data.
            request_data = RequestData(headers, io.BytesIO())
            self.stream_data[stream_id] = request_data

    def path2coordinations(self, path):
        return path.split('/')[-1]

    def handle_push_get(self, request_data, stream_id):
        # Respond to a push supporting stream
        if request_data[0] == 'push':
            self.respond_and_push(request_data, stream_id)
            return

        if request_data[0] == 'get':
            gps_point = request_data[1]
            file = open(METADATA, 'r')
            meta_json = json.load(file)
            route = meta_json['route']
            file.close()

            city = ''

            for index in range(0, len(route)):
                pos = route[index]

                if gps_point == str(pos):
                    print("Client is at index: " + str(index))
                    if index <= 87:
                        city = "espoo"
                    elif index > 87:
                        city = "helsinki"
                    print("Client is in " + city)

            if city != '':
                file_path = os.path.join(STATIC_FOLDER, city + ".json")
                if os.path.exists(file_path):
                    # Call the respond_and_push function to send the file
                    # as there is only 1 filename in the call, so push is not done
                    self.respond_and_push(["get", city], stream_id)
                    return

            # GPS point not found respond with a 404
            response_headers = (
                (':status', '404'),
                ('content-length', '0'),
                ('server', 'asyncio-h2'),
            )
            self.conn.send_headers(
                stream_id, response_headers, end_stream=True
            )
            self.transport.write(self.conn.data_to_send())
            return

        # self.conn.send_headers(stream_id, response_headers)
        # asyncio.ensure_future(self.send_data(data, stream_id))
    
    def handle_post(self, imageFileName, request_data, stream_id):
        '''
        Attempts to create the resource and then sends response to client.
        '''
        isStored = self.store_image(
                imageFileName,
                request_data.data.getvalue()
            )

        if isStored:
            # respond with 201 OK_CREATED
            self.send_response_headers(201, stream_id)
        else:
            # respond with 500 INTERNAL_SERVER_ERROR
            self.send_response_headers(500, stream_id)
            print('Error the image has not been stored')
        return

    def handle_put(self, imageFileName, request_data, stream_id):
        resourceExisted = False
        imageFullFileName = self.image_full_path(imageFileName)
        sent_file_bytes = request_data.data.getvalue()
        # check resource is in fs
        if os.path.isfile(imageFullFileName):

            # checks if resource is the same as the one uploaded, if so
            # notifies to the client
            with open(imageFullFileName, 'rb') as storedFile:
                stored_file_bytes = storedFile.read()
                if stored_file_bytes == sent_file_bytes:
                    print(f"Resource {imageFileName} already " + \
                          "existing, doing nothing.")
                    resourceExisted = True
                    # respond with 200 OK
                    self.send_response_headers(200, stream_id)

        if not resourceExisted:
            print(f"Updating/creating resource {imageFileName}")
            self.handle_post(imageFileName, request_data, stream_id)

    
    def stream_complete(self, stream_id: int):
        """
        When a stream is complete, we can send our response.
        """
        try:
            request_data = self.stream_data[stream_id]
        except KeyError as e :
            print(e)
            # Just return, we probably 405'd this already
            return

        if isinstance(request_data, List):
            self.handle_push_get(request_data, stream_id)
            return
        else:
            headers = request_data.headers

            #     body = request_data.data.getvalue().decode('utf-8')

            # data = json.dumps(
            #     {"headers": headers, "body": body}, indent=4
            # ).encode("utf8")


            # self.send_response_headers(200, stream_id, False,
            #                 'application/json', str(len(data)) )
            # asyncio.\
            #     ensure_future(self.send_data(data, stream_id))

        if headers[':method'] == 'POST':
            imageFileName = self.path2coordinations(headers[':path'])
            self.handle_post(imageFileName, request_data, stream_id)

        elif headers[':method'] == 'PUT':
            imageFileName = self.path2coordinations(headers[':path'])
            self.handle_put(imageFileName, request_data, stream_id)

    def respond_and_push(self, variables, stream_id):

        # Get the file path and then the json from the file and dump it to string and encode for sending
        file_path = os.path.join(STATIC_FOLDER, variables[1] + ".json")
        file = open(file_path, 'r')
        json_from_file = json.load(file)
        data = json.dumps(json_from_file).encode("utf8")
        file.close()

        # response headers to the GET requests
        response_headers = (
            (':status', '200'),
            ('content-type', 'application/json'),
            ('content-length', str(len(data))),
            ('server', 'asyncio-h2'),
        )

        # stream id for the Push stream
        next_stream_id = self.conn.get_next_available_stream_id()

        # Check if there are other paths in the request that we can push
        if len(variables) > 2:
            file_path2 = os.path.join(STATIC_FOLDER, variables[2] + ".json")
            if os.path.exists(file_path2):
                # PUSH Promise headers
                request_headers = [
                    (':method', 'GET'),
                    (':authority', u'example.localhost'),
                    (':scheme', 'https'),
                    (':path', ('push/' + variables[2])),
                    # ('user-agent', 'hyper-h2/1.0.0'),
                ]

                # PUSH Promise- https://python-hyper.org/projects/h2/en/stable/api.html <- conn.push_stream()
                self.conn.push_stream(stream_id, next_stream_id, request_headers)
                print("push promise sent")

        # Send headers and data of the first request
        self.conn.send_headers(stream_id, response_headers)
        self.conn.send_data(stream_id, data, end_stream=True)
        self.transport.write(self.conn.data_to_send())
        print(variables[1] + ".json sent")

        if len(variables) > 2:
            file_path2 = os.path.join(STATIC_FOLDER, variables[2] + ".json")
            if not os.path.exists(file_path2):
                # cancel the push as the files can't be found
                print("no push done because of invalid file name")
                return
        else:
            print("no push done because of no more file names")
            return

        # PUSH data
        file2 = open(file_path2, 'r')
        json_from_file2 = json.load(file2)
        data2 = json.dumps(json_from_file2).encode("utf-8")
        file2.close()

        # PUSH headers
        response_headers2 = (
            (':status', '200'),
            ('content-type', 'application/json'),
            ('content-length', str(len(data2))),
            ('server', 'asyncio-h2'),
        )

        # Simulate the calculated delay that makes sure the consecutive map is sent
        # in an optimal time window, before the client requests the next one manually.
        time.sleep(5)

        # PUSH
        self.conn.send_headers(next_stream_id, response_headers2)
        self.conn.send_data(next_stream_id, data2, end_stream=True)
        print(variables[2] + " pushed")

    def send_response_headers( self,
            statusCode,
            stream_id,
            terminate_stream=True,
            contentType=None,
            contentLength=0,
    ):
            """
            Builds response headers.
            
            statusCode - must be specified;
            stream_id - stream where to send the header frame, default yes;
            terminate_stream - True if you want to close the stream after sending the frame;
            contentType - by default None, a possible one is application/json;
            contentLength - by default 0, add if the request has a body.
            """
            response_headers = [
                (':status', str(statusCode)),
                ('content-length', str(contentLength)),
                ('server', SERVER_NAME), # set in the beginning
            ]
            if contentType is not None:
                response_headers.append(
                    ('content-type', contentType)
                )
            self.conn.send_headers(stream_id=stream_id,
                                   headers=response_headers,
                                   end_stream=terminate_stream
            )
            
    def receive_data(self, data: bytes, stream_id: int):
        """
        We've received some data on a stream. If that stream is one we're
        expecting data on, save it off. Otherwise, reset the stream.
        """
        try:
            stream_data = self.stream_data[stream_id]
            print(len(data))
            # flow control requires ack
            self.conn.acknowledge_received_data(
                len(data),
                stream_id
            )
        except KeyError as e:
            print(e)
            print(f"Error inbound streaming on stream {stream_id}")
            self.conn.reset_stream(
                stream_id, error_code=ErrorCodes.PROTOCOL_ERROR
            )
        else:
            stream_data.data.write(data)

    def image_full_path(self, imageName):
        return os.path.join(
                SERVER_STORAGE, imageName
            )

            
    def stream_reset(self, stream_id):
        """
        A stream reset was sent. Stop sending data.
        """
        if stream_id in self.flow_control_futures:
            future = self.flow_control_futures.pop(stream_id)
            future.cancel()

    async def send_data(self, data, stream_id):
        """
        Send data according to the flow control rules.
        """
        while data:
            while self.conn.local_flow_control_window(stream_id) < 1:
                try:
                    await self.wait_for_flow_control(stream_id)
                except asyncio.CancelledError as e:
                    print(e)
                    return

            chunk_size = min(
                self.conn.local_flow_control_window(stream_id),
                len(data),
                self.conn.max_outbound_frame_size,
            )

            try:
                self.conn.send_data(
                    stream_id,
                    data[:chunk_size],
                    end_stream=(chunk_size == len(data))
                )
            except (StreamClosedError, ProtocolError) as e:
                print(e)
                # The stream got closed and we didn't get told. We're done
                # here.
                break

            self.transport.write(self.conn.data_to_send())
            data = data[chunk_size:]

    async def wait_for_flow_control(self, stream_id):
        """
        Waits for a Future that fires when the flow control window is opened.
        """
        f = asyncio.Future()
        self.flow_control_futures[stream_id] = f
        await f

    def window_updated(self, stream_id, delta):
        """
        A window update frame was received. Unblock some number of flow control
        Futures.
        """
        if stream_id and stream_id in self.flow_control_futures:
            f = self.flow_control_futures.pop(stream_id)
            f.set_result(delta)
        elif not stream_id:
            for f in self.flow_control_futures.values():
                f.set_result(delta)

            self.flow_control_futures = {}
    
    def store_image(self, newImageFileName, imageBytes):
        '''
        This stores and displays the image received from the client
        '''
        if len(imageBytes) > 0:
            # shows image
            if args.show:
                with Image.open(io.BytesIO(imageBytes)) as image:
                    image.show()
            # stores image
            newImagePath = self.image_full_path(newImageFileName + '.jpg')
            with open(newImagePath, 'wb+') as newImageFile:
                newImageFile.write(imageBytes)
            successful = True
        else:
            successful = False
        return successful


# In order to decrypt TLS traffic on wireshark do:
# 1. execute pip install -r requirements (sslkeylog library needs to be installed)
# 2. set SSLKEYLOGFILE environment variable to point to the file which will contain the TLS logging.
# 3. See the last part of the tutorial (https://jimshaver.net/2015/02/11/decrypting-tls-browser-traffic-with-wireshark-the-easy-way/) to tell Wireshark where the file pointed by SSLKEYLOGFILE is. 
print(f"Logging TLS key in {os.environ['SSLKEYLOGFILE']}")
sslkeylog.set_keylog(os.environ['SSLKEYLOGFILE'])

ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.options |= (
        ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_COMPRESSION
)
ssl_context.set_ciphers("ECDHE+AESGCM")
ssl_context.load_cert_chain(certfile="cert/example.crt", keyfile="cert/example.key")
ssl_context.set_alpn_protocols(["h2"])

loop = asyncio.get_event_loop()

# Each client connection will create a new protocol instance
coro = loop.create_server(
    H2Protocol, '127.0.0.1', 8822, ssl=ssl_context
)

server = loop.run_until_complete(coro)

# Serve requests until Ctrl+C is pressed
print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

# Close the server
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
