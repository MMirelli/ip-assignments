import json
import os
import ssl
import time
import re
import logging
import argparse
import multiprocessing

import paho.mqtt.client as mqtt

import sslkeylog

import shared

#===========config=======================
LOGGER, PARSER = shared.config('pub')

PARSER.add_argument('--taskN',
                    default=2,
                    choices=[1,2,3],
                    type=int,
                    help=
'''For demo: select task number.
'''
)

PARSER.add_argument('--msgN',
                    default=10,
                    type=int,
                    help=
'''number of messages to send to a topic. 
Better if even number, they will be divided
in two batches.

    Default:10
'''
)

PARSER.add_argument('--unsub',
                    default=[f'sub{i}' for i in range(9)],
                    nargs='*',
                    type=list,
                    help=
'''List of subscribers to be unsubscribed from
the current topic. For demo: task2.

    Default: sub0, sub1, sub2, sub3, sub4, 
               sub5, sub6, sub7, sub8
'''
)

PARSER.add_argument('--pubN',
                    default=1,
                    type=int,
                    help=
'''Number of publishers, each sending messages on
a different topic

    Default: 1
'''
)

args = PARSER.parse_args()

taskN = args.taskN


#===============pub_tasks_utils=========================

def connect_pub(pubName):
    client = mqtt.Client(pubName)
    client.on_publish = on_publish  # callback in paho

    # In order to decrypt TLS traffic on wireshark do:
    # 1. execute pip install -r requirements.txt (sslkeylog library needs to be installed)
    # 2. set SSLKEYLOGFILEASS2 environment variable to point to the file which will contain the TLS logging.
    # 3. See the last part of the tutorial
    # (https://jimshaver.net/2015/02/11/decrypting-tls-browser-traffic-with-wireshark-the-easy-way/)
    # to tell Wireshark where the file pointed by SSLKEYLOGFILE is.
    # e.g.(Windows:Powershell)>
    # [Environment]::SetEnvironmentVariable("SSLKEYLOGFILEASS2", "C:\Users\Sane\proj\logs\sslkeylog.log", "User")
    LOGGER.info(f"Logging TLS key in {os.environ['SSLKEYLOGFILEASS2']}")
    sslkeylog.set_keylog(os.environ['SSLKEYLOGFILEASS2'])

    # TLS
    client.tls_set(shared.CA_FILE, tls_version=ssl.PROTOCOL_TLS)
    client.connect(shared.BROKER, shared.PORT)
    return client


def send_data(pub, startI, endI, topic):

    with open('data/1577541737.json', 'r') as data_file:
        data = data_file.read()

    roads = json.loads(data)

    msgSent = 0
    for i in range(startI, endI):
        # message = f'# {i}'
        message = json.dumps(roads[i])
        time.sleep(0.2)
        pub.publish(topic, message)
        msgSent += 1
    return msgSent

def send_control(pub, unsubs, topic):
    msgSent, stats = 0, ''
    for unsub in unsubs:
        # kills three subs
        data_sent = pub.publish(topic,
                        f'###STOP-{unsub}###')
        time.sleep(.4)
        stats += f'(nSubs - {msgSent})+'
        msgSent += 1
    return msgSent, stats

# define what to publish
def on_publish(client, userdata, result):
    LOGGER.info(f'{shared.get_cl_id(client)}-data was published')

    
def pub_to_topic(pub):
    pubId = shared.get_cl_id(pub)
    index = re.findall(r'\d+', pubId)[0]
    return f'topic{index}'
    
#=========pubs_for_taks=========================
def run_pub_task1(pub):
    # max 340 without loosing messages
    msgN = args.msgN
    
    topic = pub_to_topic(pub)
    
    # send the first batch of data messages
    msgN = send_data(pub, 0, msgN, topic)

    # stops all subscribers
    pub.publish(topic, '###STOP###')
    controlMsgSent = 1

    LOGGER.info(f'Data messages sent: {msgN}')
    LOGGER.info(f'Control messages sent: {controlMsgSent}')

def run_pub_task2(pub):
    # max 340 without loosing messages
    msgN = args.msgN  
    
    # subscribers to be unsubscribed
    unsubs = [''.join(s) for s in args.unsub] 
    halfMsgs = int(msgN/2)
    msgN = halfMsgs * 2

    topic = pub_to_topic(pub)

    # send the first batch of data messages
    firstBatchSent = send_data(pub, 0, halfMsgs, topic)
    finalStat = f'(nSubs * {firstBatchSent})+'

    # send unsubscribe control messages
    tmpContMsg, tmpfinalStats = send_control(pub, unsubs, topic)
    controlMsgSent = tmpContMsg
    finalStat += tmpfinalStats

    # send the second batch of data messages
    sndBatchSent = send_data(pub, halfMsgs, msgN, topic)

    finalStat += f'((nSubs - {controlMsgSent})  * {sndBatchSent})+'

    # stop all clients on the current topic
    pub.publish(topic, '###STOP###')
    controlMsgSent += 1
    # last control messages sent
    finalStat += f'(nSubs - {len(unsubs)})'

    dataMsgSent = firstBatchSent + sndBatchSent
    LOGGER.info(f'Data messages sent: {dataMsgSent}')
    LOGGER.info(f'Control messages sent: {controlMsgSent}')

    msgStats = 'Verify number of msgs received by:\n'
    finalStat = 'eval(\'' + finalStat + '\', {\'nSubs\': })'

    LOGGER.info(f'{msgStats + finalStat}')

def run_pub_task3():
    msgN = args.msgN  
    pubN = args.pubN
    pubs = []
    for i in range(pubN):
        curPub = connect_pub(f'pub{i}')
        pubs.append(curPub)
    

#    jobs = []
    dataSent = 0
    for pub in pubs:
        dataSent+=send_data(pub, 0, msgN,
                    f'{pub_to_topic(pub)}')
        # why is this not working
        #           |||
        #           VVV
        # topic = pub_to_topic(pub)
        # print('trying to publish')
        # j = multiprocessing.Process(
        #     target=pub.publish,
        #     args=(topic, '###STOP###')
        # )
        # i += 1
        # jobs2.append(j)
        # j.start()
    # for j in jobs2:
    #     j.join()
    controlSent = 0
    for pub in pubs:
        time.sleep(.5)
        pub.publish(pub_to_topic(pub), '###STOP###')
        controlSent += 1
    
    LOGGER.info(f'data messages sent: {dataSent}')
    LOGGER.info(f'control messages sent: {controlSent}')

#===================main======================
client = connect_pub('pub1')

# publisher for task1 in demo
if taskN == 1:
    run_pub_task1(client)
    
# publisher for task2 in demo
if taskN == 2:
    run_pub_task2(client)

if taskN == 3:
    run_pub_task3()

LOGGER.info('stopping')
