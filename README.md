### IP-2020

In these projects, I have explored a few cutting-edge Internet Protocols including HTTP/2, MQTT, HLS, DASH and WebRTC. The assignment were completed in groups of three members. I am grateful to S.V. and R.O. for having been members of my team in these small projects.

-------

##### Setup instruction

Assignments 1 and 2 need some dependecies to be installed:

`pip install -r requirements.txt`

Assignment 3 can be executed on any browser (just open [index.html](./part3/webrtc/index.html)). 

> If you wish to test the playback delay, please follow the instruction in [main.js](./part3/webrtc/js/main.js) to find out how.

-------

##### Assignment 1 - HTTP/2 server with python [hyper-h2 stack](https://python-hyper.org/projects/h2/en/stable/basic-usage.html)

We were asked to build a HTTP2 client and server, and an encrypted connection  (using TLS) between them. 

The methods the server offers are:

* `GET`;
* `PUT`;
* `POST`;
* `PUSH`.

The incoming and outcoming data consists of images.

My work was mainly focused on the [`GET`](./part1/clients/get.py), [`PUT`](./part1/clients/post.py), [`POST`](./part1/clients/post.py) client/[server
](./part1/server.py) implementations and Wireshark measurements of the performances beetwen `POST` and `PUT`.

-------

##### Assignment 2 - Pub/Sub Services using [paho-mqtt](https://pypi.org/project/paho-mqtt/)

We were ask to set up a communication between many subscribers and publisher sending json files using MQTT. The files would be encrypted (using TLS) and transmitted from publishers to subscribers and ingested in a sqlite database. 

As for the performance analysis, we were required to measure the delay and the transmission rate with a large number of peers.

My focus was in developing:

* TLS connection;
* [broker containerization](./part2/broker);
* [pub solution](./part2/pub.py);
* [multi subscriber](./part2/sub_gen_complex.py);
* [statistics](./part2/img) based on wireshark measurements.

-------

##### Assignment 3 - Video Streaming with [WebRTC](https://webrtc.org)

The assignment requested to measure the behaviour of few (at least two) video streaming protocols in one-to-many and many-to-one scenarios. We experimented HLS, DASH and WebRTC.

Personally, I worked on [WebRTC](./part3/webrtc), implementing a p2p solution to stream video data collected from the system webcam, and computed the playback delay statistics.
