#!/usr/bin/python
# Processes json files with collected beamsplitter data
import numpy
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import json

import argparse

parser = argparse.ArgumentParser()

parser.add_argument('--old', action='store_true', help = '')
parser.add_argument('--text', action='store_true', 
            help = 'Set for not showing graphs but only saving them')

parser.add_argument("jsonFileName", help = 'The name of the input json file')
args = parser.parse_args()

import sys # 

try:
	with open(args.jsonFileName, "rt") as fileJson :
		collection = json.load(fileJson)
except IOError:
	print "Cannnot open file with collected data"
	raise

if len(collection) == 0:
    print "Empty dataset is retrieved"
    sys.exit(1)

# For now we just look at a single representer (middle, term)
item = collection[0]['data']

def getarray(item, field):
    return numpy.array([item[j][field] for j in range(len(item))])

vert = getarray(item, 'vertical')
freq = getarray(item, 'frequency')
flux0 = getarray(item, 'flux0')
flux10 = getarray(item, 'flux10')
flux20 = getarray(item, 'flux20')

fig1, ax1 = plt.subplots()
ax1.scatter(freq, vert, c=flux0, s=25, marker = 's', edgecolors = 'none')

fig2, ax2 = plt.subplots()
ax2.scatter(freq, vert, c=flux10, s=25, marker = 's', edgecolors = 'none')

fig3, ax3 = plt.subplots()
ax3.scatter(freq, vert, c=flux20, s=25, marker = 's', edgecolors = 'none')

fig1.savefig('flux0.png', bbox_inches= 'tight')
fig2.savefig('flux10.png', bbox_inches= 'tight')
fig3.savefig('flux20.png', bbox_inches= 'tight')

# Now, the same but for scatter

fig31 = plt.figure()
fig31.clf()
ax31 = Axes3D(fig31)
ax31.plot(freq, vert, flux0)
ax31.set_title('Flux 0')

fig32 = plt.figure()
fig32.clf()
ax32 = Axes3D(fig32)
ax32.plot(freq, vert, flux10)
ax32.set_title('F_1 / F_0')

fig33 = plt.figure()
fig33.clf()
ax33 = Axes3D(fig33)
ax33.plot(freq, vert, flux20)
ax33.set_title('F_2 / F_0')

fig31.savefig('3dflux0.png', bbox_inches= 'tight')
fig32.savefig('3dflux10.png', bbox_inches= 'tight')
fig33.savefig('3dflux20.png', bbox_inches= 'tight')

if not args.text :
    plt.show()