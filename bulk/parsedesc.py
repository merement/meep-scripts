# parse data files obtained for continuous spectrum

import numpy
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

import json

# to dump numpy arrays
class NumpyAwareJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, numpy.ndarray) and obj.ndim == 1:
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

import pandas

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('desc_file', help = 'Name of the pattern file')
parser.add_argument('--text', action='store_true', 
            help = 'Set for not showing graphs but only saving them')
parser.add_argument('--old', action='store_true', 
    help = 'Set for absent dot separating file name and counter')

parser.add_argument('-o', default = 'Collected', 
                    help = 'Name of the file where the processed data will be saved')

parser.add_argument('--scatter', action = 'store_true', help = 'Plot scatter')
parser.add_argument('--flat', action = 'store_true', help = 'Plot pcolor like')

args = parser.parse_args()

Tolerance = 1e-8

import sys

print "IMPORTANT! This version deals only with continuous spectrum"

try:
    with open(args.desc_file, 'r') as descf :
        content = descf.readlines()
except IOError:
    print "Couldn't open the description file"
    raise

def getvalue(line) :
    pos = line.find(':') + 2
    if pos == 1 :
        print "The description file is of unknown format"
        raise IOError
    pos2 = line.find(' ', pos)
    if pos2 < 0 :
        return float(line[pos:])
    else :
        return float(line[pos:pos2])

def getdir(line):
    pos = line.find('-->')
    if pos < 0 :
        print "The description file is of unknown format"
        raise IOError
    return line[line.find(' ', pos) + 1:].strip()

listrecs = []
for line in content :
    if line.find('Vertical spacing') >= 0 :
        cur_vert = getvalue(line)
        continue
    if line.find('Terminator length') >= 0:
        cur_term = getvalue(line)
        continue
    if line.find('middle part') >= 0 :
        cur_mid = getvalue(line)
        continue
    if not args.old :
        if line.find('Type of source') >= 0:
            pos = line.find(':') + 1
            cur_type = line[pos:].strip()
            continue
    else :
        cur_type = 'continuous'

    if line.find('Central frequency') >= 0:
        cur_cent = getvalue(line)
        place = getdir(line)
        listrecs.append({'vertical' : cur_vert, 'terminator' : cur_term,
            'middle' : cur_mid, 'frequency' : cur_cent, 
            'dir' : place, 'source' : cur_type})
# end loop over lines

print "%s records were processed" % len(listrecs)

# we make a collection of 2d arrays
# col_item = {'terminator' : .. , 'middle': ..., 'source' : pulse/continuous,
#       'data' : {
#       'vertical': [..list of verts..], 'frequency': [.. list of freqs],
#       'flux0': [2d array], 'flux1': .., 'flux2': .. ,
#       'flux10' : [2d array transfer], 'flux20': [2d array backscattering]}
#        }

def additem (col, rec):
    newitem = {'terminator': rec['terminator'], 'middle': rec['middle'], 'source': rec['source'],
            'data' : []}
    col.append(newitem)
    return newitem

def expanditem(item, rec):
    datname_start = rec['dir'].find('_') + 1
    if datname_start == 0 :
        print "The directory name is not standard"
        raise IOError

    if args.old :
        prename = rec['dir'][datname_start:]
        pos_dot = prename.rfind('.')
        datname = prename[:pos_dot] + prename[pos_dot + 1:] + ".dat"
    else :
        datname = rec['dir'][datname_start:] + ".dat"
    try:
        dat = pandas.read_csv("%s//%s" %(rec['dir'], datname), delimiter = ',').values
    except IOError :
        print "Dat-file %s at %s couldn't be open" % (datname, rec['dir'])
        sys.exit(1)
    
    dat = numpy.array(dat[:, 1:])
    nFreq = len(dat[:,0])
    locTolerance = abs(dat[-1:0] - dat[0:0])/float(nFreq)*1.5
    center = int(nFreq/2)
    
    if abs(dat[center,0] - rec['frequency']) > locTolerance:
        print "Dat-file at %s doesn't match the description" % rec['dir']
        raise IOError
    
    fluxes = dat[center, 1:]
    fluxes[-1] = abs(fluxes[-1])
    item['data'].append({'frequency': rec['frequency'], 
        'vertical': rec['vertical'], 'flux0' : fluxes[0], 
        'flux10' : fluxes[1]/fluxes[0], 'flux20' : fluxes[2]/fluxes[0]})
# end of expanditem

def inlist(col, mid, term):
    res = None
    for item in col :
        if abs(item['middle'] - mid) < Tolerance \
            and abs(item['terminator'] - term) < Tolerance :
            res = item
            break
    return res
# end of inlist

collection = []

for record in listrecs :
    inlistTerm = inlist(collection, record['middle'], record['terminator'])
    if inlistTerm == None:
        inlistTerm = additem(collection, record)

    expanditem(inlistTerm, record)
# end of loop over records



if len(collection) == 0:
    print "Empty dataset is retrieved"
    sys.exit(1)

# now we dump the processed data
with open(args.o + '.json', 'wt') as out:
    res = json.dump(collection, out, sort_keys=True, indent=4, 
                    separators=(',', ': '), cls = NumpyAwareJSONEncoder)

if not (args.flat or args.scatter) :
    sys.exit(0)
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

if not args.text :
    plt.show()
