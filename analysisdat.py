#!/usr/bin/python
# For plotting the dat-files produced by Meep
#
# ver 2015-3-18
# 
# TODO: add the option for not doing the ratio

import numpy
import matplotlib.pyplot as plt

import pandas # for reading csv

import sys 

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--old', action='store_true', help = 'Set for flipping first two observers')
parser.add_argument('--text', action='store_true', help = 'Set for not showing graphs but only saving them')
parser.add_argument('datfile')
args = parser.parse_args()

def is_number(s):
# taken from http://stackoverflow.com/questions/354038/how-do-i-check-if-a-string-is-a-number-in-python
	try:
		float(s)
		return True
	except ValueError:
		return False
    

print "Processing ", args.datfile
try:
	dat = pandas.read_csv(args.datfile, delimiter = ',').values
except IOError :
	sys.exit("File couldn't be open. Wrong name?")

# just in case we check that the first column contains labels
xcol = 0 if is_number(dat[0,0]) else 1

# xcol - frequency
# xcol + k - data from the k-th observer

numObs = dat.shape[1] - xcol -1 # number of observers
data = numpy.array(dat[:,xcol:])
xcol = 0

# in some versions the straight observer is the second one
if args.old :
	print "Old version is assumed: first two columns are flipped"
	data[:,(1,2)] = data[:,(2,1)]

f1, ax1 = plt.subplots()
# first we plot all the data
listobs = []
for i in range(numObs):
	ycol = xcol + i + 1
	ax1.plot(data[:, xcol], data[:, ycol], '.-')
	listobs.append('Sensor: %s' % i)
ax1.legend(listobs, loc = 'upper left')

f2, ax2 = plt.subplots()
# now we want results normalized by the straight observer
listrats = []
for i in range(numObs -1):
	rat = abs(data[:,i + 2]/data[:,xcol + 1])
	ax2.plot(data[:,xcol], rat, '.-')
	listrats.append('F_%s/F_0' % (i + 1))
ax2.legend(listrats, loc = 'upper left')

f1.savefig('fluxes.png', bbox_inches= 'tight')
f2.savefig('ratio.png', bbox_inches= 'tight')

if not args.text: 
	plt.show()