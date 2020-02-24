import os
import json
import argparse

STATIC_FILES_PATH = os.path.join('..', 'demo', 'static')

def extract_coordinates(coordinates_selector):
    '''
    It extracts the coordinates of espoo.json or helsinki.json depending on the file_selector input.

        file_selector - 0 for espoo, 1 for helsinki
    '''
    data_file = 'metadata.json' 
    fileFullname = os.path.join(
        STATIC_FILES_PATH, data_file
    )
    with open(fileFullname) as json_file:
        parsed = json.load(json_file)

    coordinations = parsed['route'][coordinates_selector]
    return ','.join([str(v) for v in coordinations]).replace('.','_')


parser = argparse.ArgumentParser()
parser.add_argument('--cooid', help='Select coordinate index', type=int, required=True, choices=range(0,209))
args = parser.parse_args()
print(extract_coordinates(args.cooid))
