import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--sender_n',
                    default=3,
                    choices=[3,6,9,12],
                    type=int,
                    help='''Select number of senders'''
)

args = parser.parse_args()
SENDER_N = args.sender_n


with open('pb_data-' + str(SENDER_N) + '.txt') as f:
    data = f.read();

framesEncoded = [0,0]
framesDecoded = [0,0]
encodingTime = [0,0]

avgEncTime = 0
avgDecTime = 0
decodingTime = [0,0]

n = 0
for l in data.split('\n'):
    if 'framesEncoded t0: ' in l:
        framesEncoded[0] = int(l.split(' ')[-1])
        
    if 'framesEncoded t1: ' in l:
        framesEncoded[1] = int(l.split(' ')[-1])

    if 'encodingTimestamp t0:' in l:
        encodingTime[0] =  int(l.split(' ')[-1])

    if 'encodingTimestamp t1:' in l:
        encodingTime[1] =  int(l.split(' ')[-1])
        
        curSub = framesEncoded[1]-framesEncoded[0]
        diffTime = (encodingTime[1]-encodingTime[0])/1000
        if curSub != 0:
            curPass = diffTime/(curSub)
            # incremental average:
            # https://math.stackexchange.com/questions/106700/incremental-averageing
            avgEncTime += (curPass - avgEncTime)/n

        
    if 'framesDecoded t0: ' in l:
        framesDecoded[0] = int(l.split(' ')[-1])

    if 'framesDecoded t1: ' in l:
        framesDecoded[1] = int(l.split(' ')[-1])

        
    if 'decodingTimestamp t0:' in l:
        decodingTime[0] =  int(l.split(' ')[-1])

    if 'decodingTimestamp t1:' in l:
        decodingTime[1] =  int(l.split(' ')[-1])
        
        n += 1
        curSub = framesDecoded[1]-framesDecoded[0]
        diffTime = (decodingTime[1]-decodingTime[0])/1000
        if curSub != 0:
            curPass = diffTime/(curSub)
            # incremental average:
            # https://math.stackexchange.com/questions/106700/incremental-averageing
            avgDecTime += (curPass - avgDecTime)/n


print('Average encoding time in 1 minute with %i senders: %f' % (SENDER_N, avgEncTime))
print('Average decoding time in 1 minute with %i senders: %f' % (SENDER_N, avgDecTime))

