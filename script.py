import os, time
from config import nodes

os.system("gnome-terminal -e 'python -u bootstrap.py'")
for node in range(1, nodes):
    time.sleep(2)
    os.system("gnome-terminal -e 'python -u rest.py -p 500" + str(node) + "'")