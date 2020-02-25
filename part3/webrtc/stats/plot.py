import numpy as np
import matplotlib.pyplot as plt
# if using a Jupyter notebook, inlcude:

sendersN = [3,6,9,12]
encDelay = [.131236, .138294, .157290, .285993]
decDelay = [.130657, .137837, .162226, .460685]
tranDelay = [ .001037, .00058086, .001152887, .00109148]
pbDelay = [ ey + ez + eq for (ey,ez,eq) in zip(encDelay, decDelay, tranDelay)]


fig, ax = plt.subplots()

plt.ylabel('s / frame')
plt.xlabel('number of senders')
plt.title('Average delay')

print(encDelay)
print(decDelay)
print(pbDelay)

plt.scatter(sendersN, encDelay, marker=',', s=100)
ax.plot(sendersN, encDelay)
plt.scatter(sendersN, decDelay)
ax.plot(sendersN,decDelay)
plt.scatter(sendersN, tranDelay)
ax.plot(sendersN,tranDelay)
plt.scatter(sendersN, pbDelay)
ax.plot(sendersN,pbDelay)

plt.xticks(sendersN)

ax.legend(['Encoding delay', 'Decoding delay', 'Transmission latency', 'Playback delay'])

plt.show()
