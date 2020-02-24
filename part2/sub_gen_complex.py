import json
import sqlite3
import ssl
from time import sleep
import re
import multiprocessing

import paho.mqtt.client as mqtt


import shared

#=================config================
logger, parser = shared.config('subs')

parser.add_argument('--taskN',
                    default=2,
                    choices=[1,2,3],
                    type=int,
                    help=
'''For demo: select task number.
'''
)

parser.add_argument('--topicN',
                    default=4,
                    choices=range(1,101),
                    type=int,
                    help=
'''Number of topics. For demo task3
    NOTE: It is important that topicN/2 divides subN.
    
    Default: 4
'''
)

parser.add_argument('--subN',
                    default=10,
                    type=int,
                    help=
'''number of subscribers to a topic
    NOTE: on S.\'s machine maximum 340

    Default:10
''',
        )

args = parser.parse_args()

#========subs_per_topic_manager============
class SubsManager:
    '''
    Manages the execution flow of several subscribers to a single topic
    Inputs:
        topicName - name of the topic
        iEnd - iEnd-1 is the id associated to the last subscriber
        iStart - id associated to the first subscriber
    Default:
        iStart = 0
    Preconditions:
        iEnd > iStart
    '''
    
    def __init__(self, manId, topicNames, subs): #, iEnd, iStart=0):
        # dynamic dictionary having as keys the subscribers and
        # as values the topics which they are subscribed to

        self.topsPerSub = {s: [t for t in topicNames] for s in subs}
        self.subN = len(subs)
        self.totMsgReceived = 0
        self.managerId = 'man' + str(manId)
        logger.info(f"{self.managerId}-Subs manager initialised")

        
    def on_connect(self, sub, userdata, flags, result):
        logger.info(shared.conc_cl_id(
            f'connection: {shared.CON_RES[result]}', sub)
        )
        
        for t in self.topsPerSub[sub]:
            logger.info(shared.conc_cl_id(
                f'subscribed to {t}', sub)
            )
            
            sub.subscribe(t)
            
    def stopMsgs(self, sub, t):
        return (
            # message stopping all subs on the on_message topic
            f'###STOP###' ,
            # message stopping the sub with a specific id
            f'###STOP-{shared.get_cl_id(sub)}###'
       )

    def on_message(self, sub, userdata, msg):
        payload = msg.payload.decode()
        self.totMsgReceived += 1

        # if the pub sends a STOP message we remove the topic from topsPerSub
        for t in (self.topsPerSub[sub]):
            stoppingMsgs = self.stopMsgs(sub, t)
            if payload in stoppingMsgs:
                logger.info(shared.conc_cl_id(
                    f'{msg.topic}: ..{payload}', sub)
                )
                # remove topic from the subscriptions dictionary
                self.topsPerSub[sub].remove(t)
                # if there are no topics for the current sub then remove it
                # from the dictionary
                if len(self.topsPerSub[sub]) == 0:
                    self.topsPerSub.pop(sub)

                logger.info(shared.conc_cl_id(
                    f"unsubscribing from {t}", sub)
                )
                # unsubscribe sub
                sub.unsubscribe(t)
                return

        # save msg to DB
        r = json.loads(payload)
        pl_name = r['road_name']
        logger.info(shared.conc_cl_id(
            f'{msg.topic}: ..{pl_name}', sub)
        )

        con = None
        try:
            con = sqlite3.connect('test.db')
            c = con.cursor()
            c_id = shared.get_cl_id(sub)
            c.execute("insert INTO roads(client_id, topic, road_name, data) values(?, ?, ?, ?)", [c_id, msg.topic, r['road_name'], payload])
            con.commit()
        except sqlite3.Error as e:
            print(e)

    def print_stats(self):
        logger.info(f'{self.managerId}-Number of subscribers: '
                    f'{len(self.topsPerSub)}')
        
        logger.info(f'{self.managerId}-Total messages received: '
                    f'{self.totMsgReceived}')
        
        if self.totMsgReceived > 0:
            logger.info(f'{self.managerId}-Avg messages/client: '
                        f'{self.totMsgReceived/self.subN}')

    def start_connection(self, sub):
        sub.tls_set(shared.CA_FILE, tls_version=ssl.PROTOCOL_TLS)
        sub.on_connect = self.on_connect
        sub.on_message = self.on_message
        sub.connect(shared.BROKER, shared.PORT)

    def run(self):
        self.print_stats()
        # create subs
        for sub in self.topsPerSub.keys():
            self.start_connection(sub)
            sub.loop_start()

        self.print_stats()

        # waits to receive at least one message 
        while self.totMsgReceived == 0:
            pass

        # waits until all subs have quit
        while len(self.topsPerSub) > 0:
            pass

        self.print_stats()

#==================utils======================
def spawn_sub(index):
    cname = "sub" + str(index)
    return mqtt.Client(cname)

#===================main======================
def main():
    taskN = args.taskN
    topicN = args.topicN
    subN = args.subN

    if taskN == 1 or taskN == 2:
        subs = []
        for i in range(subN+5):
            sub = spawn_sub(i)
            # in this way we prove task1.2
            if i < subN:
                subs.append(sub)
        manager1 = SubsManager(1, ['topic1'], subs)
        manager1.run()
    else:
        topicsPerSet = int(topicN / 2)
        # we subscribe each sub to at least 2 topics each
        # sending from two pubs. In the way we are doing
        # below we will have two sets of topics with each 
        # sub subscribed to one of them
        subsPerSetOfTopics = int(subN / 2)
        
        topicSet1, topicSet2 = [], []
        for i in range(topicsPerSet):
            topicSet1.append(f'topic{i}')
            topicSet2.append(f'topic{i+topicsPerSet}')

        subs1, subs2 = [], []
        for i in range(subsPerSetOfTopics):
            sub1 = spawn_sub(i)
            sub2 = spawn_sub(i+subsPerSetOfTopics)
            subs1.append(sub1) 
            subs2.append(sub2)

        
        manager1 = SubsManager(1, topicSet1, subs1)
        manager2 = SubsManager(2, topicSet2, subs2)

        p1 = multiprocessing.Process(target=manager1.run)
        p2 = multiprocessing.Process(target=manager2.run)

        p1.start()
        p2.start()
        
        p1.join()
        p2.join()

if __name__ == '__main__':
    main()
