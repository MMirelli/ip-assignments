import logging

import argparse

def config(loggerName):
    '''
    It configures logging and arg parsing
    '''
    FORMAT = '%(name)s| %(asctime)s [%(levelname)s] >> %(message)s'
    logging.basicConfig(level=logging.DEBUG,
                        format=FORMAT,
                        datefmt='%m-%d %H:%M:%S')
    logger = logging.getLogger('ass2/'+loggerName)
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter
    )
    return logger, parser

CA_FILE = './broker/config/ca_certs/ca.crt'
BROKER = 'localhost'
PORT = 8883

CON_RES = {0: 'connection successful',
           1: 'incorrect protocol',
           2: 'invalid sub-id',
           3: 'server unavailable',
           4: 'bad credentials',
           5: 'not authorised'
} 

def get_cl_id(client):
    return client._client_id.decode('utf8')

def conc_cl_id(msg, client):
    client_id = get_cl_id(client)
    return f'{client_id}-' + msg
