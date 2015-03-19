#!/bin/bash

python genpatts.py --continuous --vert 6.2:8 gen.ini.patt 
chmod a+x gen.patt.sh
./gen.patt.sh
chmod a+x crawl_gen.patt.sh
chmod a+x crawl_plot_gen.patt.sh
# ./crawl_gen.patt.sh > crawl.log &