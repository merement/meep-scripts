#!/usr/bin/env python
# Some basic analysis of 1d data presented in h5 files
# Hopefully it will result in something meaningful
#
# ver 2015-4-20

import numpy
from scipy import fft, arange
#import cmath 
#import pandas # for reading/writing csv
import sys

import h5py

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--text', action='store_true', help = 'Set for not showing graphs but only saving them')
parser.add_argument('--time', action='store_true', help = 'Show time dependency')
parser.add_argument('--spectrum', action='store_true', help = 'Show spectrum')
parser.add_argument('--out', default = None, help = 'Outputs relative phases into a dat file')
parser.add_argument('datfile', nargs='+')
args = parser.parse_args()

if args.text :
	from matplotlib import use
	use('Agg')

import matplotlib.pyplot as plt

inp_files = args.datfile # .split(" ")
num_files = len(inp_files)

print "Processing ", args.datfile
try:
	fdata = [h5py.File(inp_files[i], 'r') for i in range(num_files)]
except IOError :
	sys.exit("File couldn't be open. Wrong name?")

# Check input files and extract names of the datasets
dsets = []
data_size = None
for i in range(num_files) :
	dkeys = fdata[i].keys()
	print "File %s contains fields %s" % (inp_files[i], dkeys)
	if not dkeys[1][-2:] in ['.i', '.r'] :
		sys.exit("The file doesn't contain complex numbers")

	dsets.append(dkeys[0][:-2])

	if not data_size :
		data_size = fdata[i][dkeys[1]].len()
	elif fdata[i][dkeys[1]].len() != data_size :
		sys.exit('Data is inconsistent')

data_re = numpy.array([fdata[i][dsets[i] + '.r'].value 
		for i in range(num_files)])
data_im = numpy.array([fdata[i][dsets[i] + '.i'].value 
		for i in range(num_files)])

data_full = data_re + 1j*data_im

f1, ax1 = plt.subplots()
f2, ax2 = plt.subplots()
f21, ax21 = plt.subplots()

listobs = []
for i in range(num_files) :
	ax1.plot(abs(data_full[i, :]))
	ax2.plot(data_re[i, :], '.-')
	ax21.plot(data_im[i, :], '.-')
	listobs.append('Port: %s' % i)

ax1.legend(listobs, loc = 'upper left')
ax1.set_xlabel('Time counts')
#f1.suptitle('Amplitude')
ax2.legend(listobs, loc = 'upper left')
ax2.set_xlabel('Time counts')
#f2.suptitle('Real part')
f1.savefig('abs.png', bbox_inches= 'tight')
f2.savefig('time_real.png', bbox_inches= 'tight')
f21.savefig('time_imag.png', bbox_inches= 'tight')

if args.time :
	f3, ax3 = plt.subplots()
	#f4, ax4 = plt.subplots()
	listobs = []
	for i in range(1, num_files) :
		ax3.plot(abs(data_full[i, 70:]/data_full[0, 70:]))
		#ax4.plot(numpy.sin(dat_ph[i, 70:] - dat_ph[0, 70:]))
		listobs.append('F_%s/F_0: ' % i)

	ax3.legend(listobs, loc = 'upper left')
	f3.suptitle('Ratio of amplitudes')
	#ax4.legend(listobs, loc = 'upper left')
	f3.savefig('abs_rel.png', bbox_inches= 'tight')
	#f4.savefig('phase_rel.png', bbox_inches= 'tight')

if args.spectrum :
	f5, ax5 = plt.subplots()
	f6, ax6 = plt.subplots()
	f7, ax7 = plt.subplots()
	f8, ax8 = plt.subplots()

	def trans(y):
		n1 = int(numpy.log2(len(y))) + 2
		Nlarge = 2**n1
		print "Points: ", Nlarge
		Y = numpy.fft.fft(y, Nlarge)
		frq = -numpy.fft.fftfreq(Nlarge) # we need with the opposite sign
		return Y, frq

	ds = []
	for i in range(num_files) :
		d_out, df = trans(data_full[i,:])
		ds.append(d_out)

	data_freq = numpy.array(df)
	data_spectrum = numpy.array(ds)

	# Now we find the appropriate spectral window
	distr = abs(data_spectrum[0,:])
	distr /= distr.sum()
	freq0 = (data_freq*distr).sum()
	dfreq0 = numpy.sqrt((distr*(data_freq - freq0)**2).sum())
	print "Center: %s, Width: %s" % (freq0, dfreq0)
	WConst = 2.5

	spw = numpy.where((freq0 - WConst*dfreq0 < data_freq) &
			(data_freq < freq0 + WConst*dfreq0))

	data_freq = data_freq[spw]
	perm = numpy.argsort(data_freq)

	print "Nfiles: ", num_files
	#data_spec = numpy.array([numpy.squeeze(data_spectrum[i,spw])[perm] 
	#		for i in range(num_files)])
	data_spec = numpy.squeeze(data_spectrum[:,spw])
	data_spec = data_spec[:,perm]
	data_freq = data_freq[perm]
	data_sp_phase = numpy.angle(data_spec)

	listobs = []
	for i in range(num_files) :
		ax5.plot(data_freq, abs(data_spec[i,:]))
		ax6.plot(data_freq, data_sp_phase[i,:])
		listobs.append('Port: %s' % i)
	ax5.legend(listobs, loc = 'upper left')
	f5.suptitle('Amplitude spectrum')
	ax6.legend(listobs, loc = 'upper left')
	f6.suptitle('Phase spectrum')

	listobs = []
	for i in range(1, num_files) :
		ax7.plot(data_freq, abs(data_spec[i,:]/data_spec[0,:]))
		ax8.plot(data_freq, 
			numpy.sin(data_sp_phase[i,:] - data_sp_phase[0,:]), '.-')
		listobs.append('F_%s/F_0: ' % i)
	ax7.legend(listobs, loc = 'upper left')
	f7.suptitle('Ratio of spectral amplitudes')
	ax8.legend(listobs, loc = 'upper left')
	f8.suptitle('Phase difference')

	if args.out != None :
		numpy.savetxt(args.out, data_sp_phase[1,:] - data_sp_phase[0,:])

	f5.savefig('abs_spectrum.png', bbox_inches= 'tight')
	f6.savefig('phase_spectrum.png', bbox_inches= 'tight')
	f7.savefig('ratio_ampl_spectrum.png', bbox_inches= 'tight')
	f8.savefig('rel_phase_spectrum.png', bbox_inches= 'tight')

if not args.text: 
	plt.show()