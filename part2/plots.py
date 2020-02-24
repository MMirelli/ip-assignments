import matplotlib.pyplot as plt; plt.rcdefaults()
import numpy as np
import matplotlib.pyplot as plt


objects = ('10:100', '50:200', '60:300', '100:400')
y_pos = np.arange(len(objects))
performance = [5.97, 15.34, 15.86, 15.94]

plt.bar(y_pos, performance, align='center', alpha=0.5)
plt.xticks(y_pos, objects)

plt.ylabel('s')
plt.xlabel('pubN:subM')
plt.title('Delay M pubs : N subs')

plt.show()


objects = ('10:100', '50:200', '60:300', '100:400')
y_pos = np.arange(len(objects))
performance = [0, 9, 32, 102]

plt.bar(y_pos, performance, align='center', alpha=0.5)
plt.xticks(y_pos, objects)

plt.ylabel('Lost packets')
plt.xlabel('pubN:subM')
plt.title('Loss M pubs : N subs')

plt.show()
