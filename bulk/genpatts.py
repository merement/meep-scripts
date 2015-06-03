#!/usr/bin/python

# Generates bunch of scripts with different parameters of Mach-Zender interferometers
#
# Usage:
# genpatts.py pattern.file
#
# Produces:
# pattern.file.sh
# crawler.sh
#
# The list of variables we need to define is
#   terminator_length
#   vertical_spacing
#   middle_length
#   middle_index
#   center_frequency # frequencies are for both sources and observers
#   width_frequency
#   out_name  # name of the output control file (prefix)
#   count # to distinguish different versions
#
# The command producing particular meta-configuration file is 
#
# sed -e "s/\${var1}/val1/" -e "s/\${var2}/val2/" ... initial.patt > conf.number

import argparse
parser = argparse.ArgumentParser()

parser.add_argument('--vert', default = '5', help = 'Range of vertical spacings')
parser.add_argument('--term', default = '2', help = 'Range of terminator lengts')
parser.add_argument('--middle', default = '1', help = 'Range of lengts of middle parts')
parser.add_argument('--mideps', default = '1', 
    help = 'Range for epsilon in the middle part')
parser.add_argument('--freq', default = '0.025:0.025:0.4', help = 'Range of frequencies')

# we need to be more precise with the width when a continuous source is provided
group = parser.add_mutually_exclusive_group()
group.add_argument('--continuous', action='store_true')
group.add_argument('--pulse', action='store_false')

parser.add_argument('patt_file', help = 'Name of the pattern file')

args = parser.parse_args()

#import sys
from datetime import datetime

import numpy

# Define the variation of parameters
def process(str) :
    pos = str.find(':')
    if pos < 0 :
        # single parameter
        return numpy.array([float(str)])

    start = float(str[:pos])
    pos2 = str.find(':', pos + 1)
    if pos2 < 0 :
        # simple interval is provided, 10 steps are assumed
        stop = float(str[pos + 1 :])
        return numpy.linspace(start, stop, 10)

    step = float(str[pos + 1: pos2])
    stop = float(str[pos2 + 1:])
    return numpy.arange(start,stop,step)
# end of process

vert = process(args.vert)
term = process(args.term)
middle = process(args.middle)
cent = process(args.freq)
mideps = process(args.mideps)

print "Generate files for the following parameters"
print "Vertical spacing: ", vert
print "Length of terminators: ", term
print "Length of the middle part: ", middle
print "Range of frequencies: ", cent

type = 'continuous' if args.continuous else 'pulse'

print "with a %s source" % type

pattFileName = args.patt_file[0]
outFileName = pattFileName + ".sh"
outctlName = pattFileName
metaFilePrefix = pattFileName

runFilePatt = "pass.sh.patt"
runFileName = "pass.sh"
plotFilePatt = "plot.sh.patt"
plotFileName = "plot.sh"

dirList = []

descFileName = "description.txt"
with open(outFileName, "w") as outfile, open(descFileName, "w") as descfile :
    outfile.write("#!/bin/bash \n")
    outfile.write("# Generated %s with %s as the pattern \n" % (datetime.now().strftime("%Y/%m/%d %H:%M"), pattFileName))
    
    descfile.write("Description of generated files\n")
    descfile.write("Generated %s with %s as the pattern \n" % (datetime.now().strftime("%Y/%m/%d %H:%M"), pattFileName))
    descfile.write("Type of source: %s\n" % type)

    descfile.write("\n Overview of the simulation: \n")
    descfile.write("Vertical: %s\n" % vert)
    descfile.write("Terminators: %s\n" % term)
    descfile.write("Middle: %s\n" % middle)
    descfile.write("Frequency: %s\n\n" % cent)

    count = 0
    for ver in vert:
        descfile.write("\n Vertical spacing: %s\n" % ver)
        for ter in term:
            descfile.write("\tTerminator length: %s\n" % ter)
            for mid in middle:
                descfile.write("\t\tLength of the middle part: %s\n" % mid)
                for cen in cent:
                    wid = cen/50.0 if args.continuous else cen*1.5
                    # print metaFilePrefix + "." + str(count)
                    metaFileName = metaFilePrefix + "." + str(count)
                    add_str = 'sed -e "s/\${count}/%s/"' % count
                    add_str += ' -e "s/\${width_frequency}/%s/" -e "s/\${center_frequency}/%s/"' % (wid, cen)
                    add_str += ' -e "s/\${out_name}/%s/"' % outctlName
                    add_str += ' -e "s/\${middle_length}/%s/"' % mid
                    add_str += ' -e "s/\${vertical_spacing}/%s/" -e "s/\${terminator_length}/%s/"' % (ver, ter)                    
                    add_str += ' %s > %s \n' % (pattFileName, metaFileName)
                    outfile.write(add_str)
                    dirName = "p_%s" % metaFileName
                    dirList.append(dirName)
                    outfile.write("mkdir %s \n" % dirName )
                    outfile.write("mv %s %s \n" % (metaFileName, dirName))
                    outfile.write("cp %s %s \n" % ("gentri3.py", dirName))
                    outfile.write("cp %s %s \n" % ("gen.rc", dirName))
                    outfile.write('sed -e "s/\${config}/%s/" -e "s/\${control}/%s/" %s > %s/%s \n' 
                                  % (metaFileName, outctlName+"."+str(count), runFilePatt, dirName, runFileName)) 
                    outfile.write('sed -e "s/\${config}/%s/" -e "s/\${control}/%s/" %s > %s/%s \n' 
                                  % (metaFileName, outctlName+str(count), plotFilePatt, dirName, plotFileName)) 
                    
                    descfile.write("\t\t\tCentral frequency: %s  --> %s \n" % (cen, dirName))
                    count += 1

crawlFileName = "crawl_"+pattFileName + ".sh"
crawlPlotFileName  = "crawl_plot_"+pattFileName + ".sh"

with open(crawlFileName, "w") as outfile, open(crawlPlotFileName, "w") as plotfile :
    outfile.write("#!/bin/bash \n")
    outfile.write("# Generated %s with %s as the pattern \n \n" % (datetime.now().strftime("%Y/%m/%d %H:%M"), pattFileName))
    plotfile.write("#!/bin/bash \n")
    plotfile.write("# Generated %s with %s as the pattern \n \n" % (datetime.now().strftime("%Y/%m/%d %H:%M"), pattFileName))    

    for dir in dirList :
        outfile.write("cd %s \n" % dir)
        outfile.write("chmod a+x %s \n" % runFileName) 
        outfile.write("qsub %s \n"  % runFileName)
        outfile.write("cd .. \n")
        
        plotfile.write("cd %s \n" % dir)
        plotfile.write("chmod a+x %s \n" % plotFileName) 
        plotfile.write("#./%s \n"  % plotFileName)
        plotfile.write("cd .. \n")        
