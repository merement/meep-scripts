#!/bin/bash
# A generic script for passing a meta-configuration file
# Usage:
#	$ passgen.sh [meta_configuration_file]
#		If the file is omitted some default value inside is used
#
# Action:
#	1. It processes the configuration file <conf> and outputs the Meep control 
#		file <conf>.ctl
#	2. If the translation is successfull the produced control file is passed to
#		Meep and its outputs are written into the respective Meep data files and
#		to <conf>.log (Meep's behavior)
#	3. Assumes that field's snapshots are in ..-ey.h5 and represents them in png files
#	4. Makes mpeg file out of these png's
#	5. ...
#	6. Processes the dat file and shows fluxes
#
# Relies on the default choice of the name of the output control file
#

if [ -z "$1" ]; then conf="gen.ini"; else conf=$1; fi

gentri3.py -i $conf
if [ $? -ne 0 ]; then
    echo "Something failed during translation"
    exit 1
fi

meep $conf.ctl | tee $conf.log
# Here we get the number of time slices
outn=`h5ls ${conf}-ey.h5 | sed -e "s/\// /" | awk '{print $5;}'`
((out=outn-100))
echo "${out} time points are detected"
h5topng -t 0:$out -R -Zc dkbluered -a yarg -A $conf-eps-000000.00.h5 $conf-ey.h5
ffmpeg -i $conf-ey.t%03d.png -vb 20M $conf.mpeg
h5topng $conf-eps-000000.00.h5
feh *.png
grep flux1: $conf.log > $conf.dat
#plotdat.py 
python analysisdat.py $conf.dat
