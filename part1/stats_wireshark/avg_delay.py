import argparse
import pandas as pd
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()

parser.add_argument('--file1_name', help='Name of the file',
                    default='PUT-209.csv')

parser.add_argument('--file2_name', help='Name of the file',
                    default='POST-209.csv')

parser.add_argument('--colPart', help='Name of the colPart',
                    default='Delay since previous TCP frame in stream')

parser.add_argument('--colTot', help='Name of the colPart',
                    default='Delay since first TCP frame in stream')

args = parser.parse_args()

my_csv = pd.read_csv(args.file1_name)
colPartF1 = my_csv[args.colPart]
colTotF1 = my_csv[args.colTot]

my_csv = pd.read_csv(args.file2_name)
colPartF2 = my_csv[args.colPart]
colTotF2 = my_csv[args.colTot]

df = pd.concat([colPartF1, colPartF2], axis=1, join='inner')
df.columns = ['PUT', 'POST']

print(df)

def add_tabs(df, n):
    return '\t'.join([str(x) for x in df.tail(n)])

print(f"\nPartial delay\n{df.mean()}\n")
n = 5
print(f"Last {n} total delays:\n\tPUT:  {add_tabs(colTotF1, n)}\n\tPOST: {add_tabs(colTotF2,n)}")

ax = df.reset_index().plot(x='index', y=['PUT', 'POST'], \
                      title='Delay since previous TCP frame in stream')
leg = plt.legend()
# get the lines and texts inside legend box
leg_lines = leg.get_lines()
plt.setp(leg_lines[1], linewidth=0.6)
ax.set_xlabel("frames")
ax.set_ylabel("(s)")

plt.show()


