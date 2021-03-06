#!/usr/bin/env python3
# Generator of scripts for Meep out of meta-configuration files
#
# by Misha Erementchouk
#
# ver of 2015-2-11
# Supports only purely horizontal or pure vertical elements.
#
# ver of 2015-2-28
# Added: normal command line options
#        fractional periods at the beginning (skip parameter) and at the end (periods + shift)
#        grooves of parallel lines may touch
#        adding comments to the control file (sources, fluxes, controls are not done)
#
# ver of 2015-03-01
# Added:
#       continuous sources
#       field snapshots (only ez)
#       better implementation of 'structure only'
# Slight cleanup
#
# ver of 2015-03-02
# Added:
#       More options for sources and snapshots
#
# ver of 2015-03-20
# Added:
#       implementation of the default name for the ctl-file
#
# ver 4-20-2015 (0.4)
# 1. Version control is added
# 2. Control of the complexity of the field
# 3. Put snapshots to collectors 
# 4. Separated spectral and temporal (transient) characteristics 
# 5. Local field snapshots
# TODO: unify local/global through specification of coordinates
# TODO: arbitrary function
# TODO: implement spectral quantities
# TODO: the design shows a lot of flaws. Implement patches in a consistent manner
# TODO: correct time decay (component)

import numpy as np
import copy # for copying nested dictionaries
import sys
import yaml
from datetime import datetime

import os

# *** Some general constants ***
# When a float is considered zero
Tolerance = 1e-6

# simple check version of metaconfigurations
# these variables can be overriden
VERSION = '0.4.1'
MAJOR_VERSION = '0.4'

def validateVersion(version) :
    # until release, x in 0.x.y denotes the major version
    if version == VERSION :
        return True
    print("The version of the meta-configuration data is not current. Possible compatibility issues may be expected.")
    # We extract the major part of the version
    sub_pos = version.find('.',version.find('.')+1)
    maj_ver = version[:(len(version) if sub_pos < 0 else sub_pos)]
    
    print(version, maj_ver, MAJOR_VERSION)

    if maj_ver == MAJOR_VERSION :
        return True
    print("The version of the meta-configuration data is not supported.")
    return False

def is_number(s):
# taken from http://stackoverflow.com/questions/354038/how-do-i-check-if-a-string-is-a-number-in-python
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def sort_pair(a, b) :
    return (a,b) if a < b else (b,a)

class clYAML(object):
    # class dealing with YAML data

    def validate(self) :
        # Here the trivial validation is performed
        #  
        return len(self.Data) > 0 and self.subvalidate()
    
    def subvalidate(self) :
        # For subclasses to do their stuff
        return True

    def __init__(self, FileName) :
        # TODO: deal with file problems better
        self.isValid = False
        self.Data = None
        self.iniFileName = FileName
        try:
            with open(self.iniFileName, "r") as f :
                self.Data = yaml.safe_load(f)
        except IOError :
            print("Meta-configuration file cannot be opened")
            raise
        self.isValid = self.validate()

    def getSection(self, toplevel, *args) :
        # Returns the branch starting from toplevel.args[0].args[1]...
        if toplevel in dict(self.Data) :
            digger = self.Data[toplevel]
            while len(args) > 0 :
                digger = digger[args.pop(0)]
            return digger
        else :
            return None

## class clYAML
    
class genResource(clYAML) :
    # the class providing the interface to the generator resources
    # It's made mostly to provide additional layer of validation
    # Currently it does nothing (two months later. not anymore)
    
    def __init__(self, rcFileName = None) :
        # the constructor accepts the name of the resource file
        if rcFileName == None :
            # look for the .rc file in the directory where the py file resides
            script_path, _ = os.path.split(os.path.realpath(__file__))
            rcFileName = os.path.join(script_path, 'gen.rc')

        super(genResource, self).__init__(rcFileName)
        
        self.version = str(self.Data['version'])
        self.majorVersion = str(self.Data['support_version']).split('.')[1]
        
    def subvalidate(self) :
        if str(self.Data['version']) == VERSION :
            return True
        
        print("The resource file has wrong version.")
        return False
        
## end of class genResource

### classes Line and CollectionLines

class collectionLines(object) :
    def __init__ (self, listLines = None) :
        self.listLines = []
        self.MinX = 0
        self.MaxX = 0
        self.MinY = 0
        self.MaxY = 0
        self.MinZ = 0
        self.MaxZ = 0        
        
        self.numElements = 0
        self.numErrors = 0
        self.bufErrors = []
        
    def setCenter(self) :
        # Finalizes reading the elements off the meta-configuration file
        self.numElements = len(self.listLines)
        self.setLimits()
            
        shift_X = -(self.MaxX + self.MinX)/2.0
        shift_Y = -(self.MaxY + self.MinY)/2.0
            
        for line in self.listLines :
            line['start']['x'] += shift_X
            line['start']['y'] += shift_Y
            line['end']['x'] += shift_X
            line['end']['y'] += shift_Y

        self.MinX += shift_X
        self.MaxX += shift_X
        self.MinY += shift_Y
        self.MaxY += shift_Y
    # end of setCenter
            
    def isInside(self, x, y) :
        if self.MinX == None :
            self.setLimits()
            return False
        return self.MinX < x < self.MaxX and self.MinY < y < self.MaxY
    
    def getLimits(self) :
        return self.MinX, self.MaxX, self.MinY, self.MaxY, self.MinZ, self.MaxZ
        
    def setLimits(self) :
        if len(self.listLines) > 0 :
            # to avoid unnecessary dealing with None's
            self.MinX = self.listLines[0]['start']['x']
            self.MaxX = self.MinX
            self.MinY = self.listLines[0]['start']['y']
            self.MaxY = self.MinY
            
        for line in self.listLines :
            if line['type'] == 'connector':
                continue
            start = line['start']
            end = line['end']
            (curMinX, curMaxX) = sort_pair(start['x'], end['x'])
            
            curMinY = min(start['y'], end['y']) - line['weak_space_down']
            curMaxY = max(start['y'], end['y']) + line['weak_space_up']
            
            self.MinX = min(self.MinX, curMinX)
            self.MaxX = max(self.MaxX, curMaxX)
            self.MinY = min(self.MinY, curMinY)
            self.MaxY = max(self.MaxY, curMaxY)            
    # end of setLimits
        
    def findLineID(self, id) :
        res = None
        for line in self.listLines :
            if "id" in dict(line) and line["id"] == id :
                res = line
                break            
        return res

    def addLine(self, add_line) :
        def adjust_for_relative(point, curline = None) :
            # The awkward second argument is to support the self-reference for end points
            if "ref" in dict(point) :
                refelem = None
                if curline != None and "id" in dict(curline) and curline["id"] == point['ref'] :
                    refelem = curline
                else :
                    refelem = self.findLineID(point['ref'])

                if refelem == None :
                    self.setError("The point refers to unknown element")
                    return False

                point['x'] += refelem[point['point']]['x']
                point['y'] += refelem[point['point']]['y']
            return True
        # end adjust_for_relative

        def is_attached(point) :
            if "attached_to" in dict(point) :
                refelem = self.findLineID(point['attached_to'])

                if refelem == None:
                    self.setError("The point tries to attach to unknown element")
                    return False # hope it won't happen before Exceptions
                # Also in the rectangular design line-end cannot be attached to line-end

                point['x'] = refelem[point['point']]['x']
                point['y'] = refelem[point['point']]['y']
                point['attached_to'] = refelem
                return True
            return False
        # end adjust_for_attachment            

        # main code of addLine
        start = add_line['start']
        end = add_line['end']
        add_property = add_line['property']

        # Finding absolute coordinates
        # First we settle the start point
        if not adjust_for_relative(start) : return False
        if is_attached(start) and not start['attached_to']['type'] == 'line':
            # lines attachment is trvial --
            # if it's connector, however, we need to adjust y and (TODO) flag the necessity to create the patch
            start['x'] += 0.5*start['attached_to']['property']['width']
            start['y'] += 0.5*add_property['width']*(-1 if start['point'] == 'end' else 1)

            start['attached_to'][start['point']]['right_attachment'] = True
            
        if not adjust_for_relative(end, add_line) : return False

        # the end point can also be set up in terms of number of periods
        if "periods" in dict(end):
            # TODO: treat end['direction']
            # if 'direction' in dict(end):
            #     direct_x = float(end['direction']['x'])
            #     direct_y = float(end['direction']['y'])
            # else :
            #     direct_x = 1.0
            #     direct_y = 0.0
            # direct_len = np.sqrt(direct_x**2 + direct_y**2)
            # if direct_len < Tolerance :
            #     self.setError("Undefined direction")
            # else :
            #     direct_x /= direct_len
            #     direct_y /= direct_len
            direct_x = 1.0
            direct_y = 0.0
            shift_x = 0.0 if not 'x' in dict(end) else float(end['x'])
            shift_y = 0.0 if not 'y' in dict(end) else float(end['y'])
            shift = np.sqrt(shift_x**2 + shift_y**2)

            end['x'] = start['x'] + shift + \
                end["periods"]*add_property['grooves']['period'] # only horizontals for now
            end['y'] = start['y']
        elif is_attached(end) and not start['attached']['type'] == 'line' :
            end['x'] -= 0.5*end['attached']['property']['width']
            end['y'] += add_property['width']*(-1  if start['point'] == 'end' else 1)
            end['attached'][end['point']]['left_attachment'] = True

        add_line['type'] = 'line'
        
        # space_up is the absolute minimum required
        # weak_space_up is the maximum needed
        add_line['space_up'] = add_property['width']/2.0 + add_property['grooves']['depth']
        add_line['weak_space_up'] = add_line['space_up'] + add_property['padding']
        add_line['space_down'] = add_property['width']/2.0 + add_property['grooves']['depth']
        add_line['weak_space_down'] = add_line['space_down'] + add_line['property']['padding']
        
        if not 'skip' in dict(add_line['start']):
            add_line['start']['skip'] = 0.0
        add_line['start']['skip'] = add_line['start']['skip'] % 1 # we want only fraction
        if abs(add_line['start']['skip'] - 1) < Tolerance or abs(add_line['start']['skip']) < Tolerance :
            add_line['start']['skip'] = 0.0
            
        # Here we deal with the z part
        add_line['property']['elevation'] = self.MaxZ
        self.listLines.append(add_line)
    # end addline
    
    def addConnector(self, add_con) :
        def adjust_for_attachment(point) :
            if "attached_to" in dict(point) :
                refelem = self.findLineID(point['attached_to'])
    
                if refelem == None:
                    self.setError("The connector tries to attach to unknown element")
                    return False # hope it won't happen before Exceptions
                # We rely on the stict ordering of elements
    
                point['x'] = refelem[point['point']]['x']
                point['y'] = refelem[point['point']]['y']
                point['attached_to'] = refelem
                point['left_attached'] = True
            return True
    
        start = add_con['start']
        end = add_con['end']
    
        if not ('attached_to' in dict(start) and 'attached_to' in dict(end)) :
            self.setError("In the present version connectors must be attached to lines")
            return False
    
        if not adjust_for_attachment(start) : return False # Exceptions
        if not adjust_for_attachment(end) : return False
    
        start['y'] -= 0.5*start['attached_to']['property']['width']
        end['y'] += 0.5*end['attached_to']['property']['width']
        start['x'] += 0.5*add_con['property']['width']
        end['x'] = start['x']
    
        add_con['type'] = 'connector'
        add_con['space_left'] = add_con['property']['width']/2.0
        add_con['space_right'] = add_con['property']['width']/2.0
        
        add_con['property']['elevation'] = self.MaxZ
        self.listLines.append(add_con)
    # end of addconnector
        
    def settleConflicts(self) :
        # Now when we have all main elements added with their absolute coordinates we need to resolve
        # CONFLICTS
        # Currently we know how to deal with two types of conflicts
        # 1. (TODO) Attachment conflict.
        #    We need to make sure that sides are covered by metallic patches
        # 2. Lines overlap
        #    In the current implementation the possible overlap between lines occurs when they are
        #    too close to each other vertically
        #    For example, strong conflict
        #    too_close_strong(r) = vert_spasing(line1(r), line2(r)) < line1.space_down + line2.space_up
        #    weak conflict
        #    too_close_weak(r) = vert_spasing(line1(r), line2(r)) < line1.space_down + line2.space_up + 2*padding
        #    The strong conflict produces an error
        #    The weak conflict should be resolved by adjusting paddings inside the range
        #    that is such r where too_close_weak(r) == True
        #
        # There are five options
        # 1.      ------
        #         ------
        #      Here we adjust weak_spaces_up/down
        # 2.        ------
        #         ----------
        #      Here we cut out the parts of the lower line
        # 3. 2 flipped
        # 4.     ------
        #     -----
        #      Here we cut out the left part
        # 5. 4 flipped
        # We keep going over the list 
        
        def isDisjoint(line1, line2):
            # within the horizonatl alignment we need only x's
            x11, x12 = line1['start']['x'], line1['end']['x']
            x21, x22 = line2['start']['x'], line2['end']['x']
            
            return (max(x11, x12) <= min(x21, x22) or min(x11, x12) >= max(x21, x22)) 
        # end of isDisjoint
        
        def y_separation(line1, line2):
            # mutual penetration
            # current implementation assumes the horizontal alignment
            upper, lower = (line1, line2) if line1['start']['y'] > line2['start']['y'] else (line2, line1)
            
            distance = upper['start']['y'] - lower['start']['y']
            return distance, upper, lower
        # end y_separation
        
        def cut_line(line, x) :
            # cuts the line at the specified point and creates a new piece out of it
            # check that the line is oriented properly 
            if line['end']['x'] < line['start']['x'] :
                self.setError("Incorrect order of line ends")
                return False

            # newline wouldn't start from the partial period
            period = line['property']['grooves']['period']
            lenLinePartial = period*(1.0-line['start']['skip'])
            lenLineNew = x - line['start']['x']
            
            newline = copy.deepcopy(line)
            # newline.end copies the properties of line.end
            # properties of newline.start and new properties of line.end are coordinates only
            y = line['end']['y']
            newline['start'] = {'x' :x, 'y': y}
            line['end'] = {'x' :x, 'y': y}
            
            lenLineNewPeriods = lenLineNew - lenLinePartial
            if lenLineNewPeriods < 0:
                # the new line starts with even larger skip
                newline['start']['skip'] = 1 + lenLineNewPeriods/float(period)
            else:
                newline['start']['skip'] = divmod(lenLineNewPeriods, period)[1]/float(period)
        
            self.listLines.append(newline) 
            return True
        # end of cut_line

        flagConflicts = True
        while flagConflicts :
            for i in range(len(self.listLines)) :
                line = self.listLines[i]
                for j in range(i + 1, len(self.listLines)) :
                    conline = self.listLines[j]
                    if isDisjoint(line, conline) :
                        continue
                    distance, up, low  = y_separation(line, conline)
                    if distance < low['space_up'] + up['space_down']:
                        self.setError("Block overlap")
                        return False
                    if distance >= up['weak_space_down'] + low['weak_space_up'] :
                        continue
                    # we come here if there's a conflict but it can be settled
                    # first we check the left end
                    xmin_up = min(up['start']['x'], up['end']['x'])
                    xmin_low = min(low['start']['x'], low['end']['x'])
                    if xmin_up < xmin_low - Tolerance :
                        if not cut_line(up, xmin_low) :
                            return False
                        break
                    elif xmin_low < xmin_up - Tolerance :
                        if not cut_line(low, xmin_up) :
                            return False
                        break
                    # the left end is okay, let's look at the right one
                    xmax_up = max(up['start']['x'], up['end']['x'])
                    xmax_low = max(low['start']['x'], low['end']['x'])
                    if xmax_low > xmax_up + Tolerance :
                        if not cut_line(low, xmax_up) :
                            return False
                        break
                    elif xmax_up > xmax_low + Tolerance :
                        if not cut_line(up, xmax_low) :
                            return False
                        break                  
                    # if we get to here the ends are aligned and we need to adjust padding only
                    up['weak_space_down'] = distance/2.0
                    low['weak_space_up'] = distance/2.0
                    break
                else:
                    continue
                break
            else:
                flagConflicts = False
                    
        return True

    def setError(self, str, code = 0) :
        # TODO: Exceptions for collection of lines
        print("Analysis Error %s: %s" % (code, str))
        self.numErrors += 1
        self.bufErrors.append((code, str))    

### end of classes Line and CollectionLines
        
### class ctlInfo and its Exceptions
class InfoException(Exception) :
    """Exceptions raised while processing the meta-configuration file"""
    def __init__(self):
        pass

class ctlInfo(clYAML) :
    # the class dealing with the configuration data
    
    # comments on the content
    numWarnings = 0
    bufWarnings = []
    numErrors = 0
    bufErrors = []
    
    def __init__(self, iniFileName = None) :
        self.zSize = -1.0 # by default structures are 2d
        
        self.colLines = collectionLines()
        self.listFluxPoints = []
        self.listSources = []
        self.listTransients = []    
        
        super(ctlInfo, self).__init__("gen.ini" if iniFileName == None else iniFileName)
        self.topComment = self.getSection('comment')
    
    
    def subvalidate (self) :
        
        if not 'version' in dict(self.Data) :
            self.setWarning('Version of meta-configuration data is not provided. Errors may be expected.', code=1)
        else :
            if not validateVersion(str(self.Data['version'])): # TODO: Exceptions
                self.setError('The version of meta-configuration data is not supported. Check your configuration file against canonical.', code=1)
                return False
            
        if "default" in dict(self.Data["Output"]["ctl_file"]) \
            and self.Data["Output"]["ctl_file"]["default"] :
            self.nameCtlFile = self.iniFileName + ".ctl"
            print("Default name for the output control file is chosen")
        else :
            self.nameCtlFile = self.Data["Output"]["ctl_file"]["name"]

        # Rearrange data a bit and check for the consistency        
            
        def addSource(source) :
            def adjust_for_relative(point) :
                # here the width is also adjusted
                if "ref" in dict(point) :
                    refelem = self.colLines.findLineID(pos['ref'])
    
                    if refelem == None :
                        self.setError("The point refers to unknown element")
                        return False
    
                    point['x'] += refelem[point['point']]['x']
                    point['y'] += refelem[point['point']]['y']
    
                    point['width'] *= refelem['property']['width']
                return True
            # end adjust_for_relative (source version)
    
            pos = source["source"]["position"]
            if not adjust_for_relative(pos) : return False
            if not self.colLines.isInside(pos['x'], pos['y']) :
                self.setWarning("The source is outside")
                
            source['source']['position']['elevation'] = self.zSize/2.0 if self.zSize > 0 else 0
            self.listSources.append(source["source"])
        # end of addsource
        
        def addFluxPoint(obs) :
            def adjust_for_relative(point) :
                # here the width is also adjusted
                if "ref" in dict(point) :
                    refelem = self.colLines.findLineID(pos['ref'])
    
                    if refelem == None :
                        self.setError("The point refers to uknown element")
                        return False
    
                    point['x'] += refelem[point['point']]['x']
                    point['y'] += refelem[point['point']]['y']
    
                    point['width'] *= refelem['property']['width']
                return True
            # end adjust_for_relative (observer version, same as for sources)            
    
            pos = obs['flux']['position']
    
            if not adjust_for_relative(pos) : return False
    
            if not self.colLines.isInside(pos["x"], pos["y"]) :
                self.setWarning("The checking point is outside")
    
            obs['flux']['position']['elevation'] = self.zSize
            self.listFluxPoints.append(obs["flux"])
            return True
        # end of addFluxPoint
        
        def addSnapshots(obs):
            self.listTransients.append(obs)
            return True
            
        def addSnapLocal(obs) :
            def adjust_for_relative(point) :
                if not "ref" in dict(point) :
                    return True
                
                refelem = self.colLines.findLineID(pos['ref'])
                if refelem == None :
                    self.setError("The point refers to uknown element")
                    return False
        
                point['x'] += refelem[point['point']]['x']
                point['y'] += refelem[point['point']]['y']
                return True
            # end adjust_for_relative (local snapshot)
            
            if 'field' in dict(obs) :
                pos = obs['field']['position']
                if not adjust_for_relative(pos) : return False
                
                if not self.colLines.isInside(pos['x'], pos['y']) :
                    self.setWarning("The field collecting point is outside")
                    
                self.listTransients.append(obs)
                return True
        # end of addSnapLocal
            
        # Here's the main code
        # Set for the vertical extension
        if 'Z_direction' in dict(self.Data['Geometry']) \
           and is_number(self.Data['Geometry']['Z_direction']['size']) :
            self.zSize = self.Data['Geometry']['Z_direction']['size']
            # We will place at z = 0 with size \pm zSize if zSize > 0
            if self.zSize > 0 :
                self.colLines.MaxZ = self.zSize/2.0
                self.colLines.MinZ = -self.zSize/2.0
        
        listElem = self.Data["Geometry"]["elements"]
        numLines = len(listElem)
        
        if numLines == 0 :
            self.setWarning("The list of elements is empty")
        else :
            count = 0
            for line in listElem :
                print("Processing element: ", count, " type: ", list(line.keys())[0])
                count += 1
                
                if 'line' in dict(line):
                    self.colLines.addLine(copy.deepcopy(line['line']))
                elif 'connector' in dict(line) :
                    self.colLines.addConnector(copy.deepcopy(line['connector']))
            # end loop over elements
            
            # IMPORTANT TODO: this should be done _after_ all elements are added since some elements
            # below can enter with absolute coordinates!
            self.colLines.setCenter()
            print("The elements are confined within (X: %s, %s) (Y: %s, %s) (Z: %s, %s)" 
                  % (self.colLines.MinX, self.colLines.MaxX, self.colLines.MinY, self.colLines.MaxY, 
                     self.colLines.MinZ, self.colLines.MaxZ))
            
            if not self.colLines.settleConflicts() :
                self.setError("Conflicts couldn't be resolved")
                return False
        # end of processing lines and connector

        # sources
        listElem = self.Data["Sources"]
        if len(listElem) == 0:
            self.setWarning("The list of sources is empty!")
        for source in listElem :
            addSource(source)

        # observation points            
        listElem = self.Data['Collectors']
        if len(listElem) == 0 :
            self.setWarning("The list of checking points is empty!")
            
        if 'spectral' in dict(listElem) :
            # add spectral observers
            listObs = listElem['spectral']
            for col in listObs :
                # TODO: implement full interface for spectral observers
                if 'flux' in dict(col) :
                    addFluxPoint(col)
                    
        if 'temporal' in dict(listElem) :
            # temporal observers (snapshots)
            listObs = listElem['temporal']
            for col in listObs :
                print("Processing temporal observable: %s" % col.keys())
                if 'snapshot' in dict(col) :
                    if not addSnapshots(col) : return False
                if 'field' in dict(col) :
                    if not addSnapLocal(col) : return False
                
        return True
    # end of subvalidate
        
    def getLines(self) :
        return self.colLines.listLines

    def setWarning(self, str, code = 0) :
        # TODO: there may be the whole variety of warnings. So...
        print("Warning %s: %s" % (code, str))
        self.numWarnings += 1
        self.bufWarnings.append((code, str))
        
    def setError(self, str, code = 0) :
        # TODO: Exceptions
        print("Translation error %s: %s" % (code, str))
        self.numErrors += 1
        self.bufErrors.append((code, str))
        
    def getNumElements(self) :
        return self.colLines.numElements
    
    def commentProvided(self, element = None) :
        if not element :
            return self.topComment
        elif 'comment' in dict(element) :
            return element['comment']
        else :
            return None

    def getCtlName(self) :
        return self.nameCtlFile

## end of class ctlInfo and its Exceptions

# class MeepControl and its Exceptions
class MeepException(Exception) :
    """Exceptions raised while processing translation to Meep controls"""
    def __init__ (self) :
        pass

class MeepControl (object) :
    # this class deals with the data going into the Meep control file
    
    # buffer is an array of strings that will be dumped into the control file
    buffer = []

    def __init__(self, outFileName, rcFileName = "gen.rc") :
        self.bufStr = "" # the current line
        self.rcData = genResource(rcFileName)
        if not self.rcData.isValid :
            sys.exit("Fatal error: The resource file is corrupted!")        
        self.FileName = outFileName
        # accumulators of flux points and transients
        self.countFluxPoints = 0
        self.lineFluxCode = ""
        self.countTransients = 0
        self.lineTransCode = ""
                
        self.Code = self.rcData.getSection("Code")
        
        # write the header
        resources = self.rcData.getSection("Header")
        self.Header = resources
        self.add_comment(resources["intro"])
        self.add_comment(resources['gendata']['header'] + datetime.now().strftime("%Y/%m/%d %H:%M"))
        self.add_comment(resources['gendata']["base"] + iniData.iniFileName)
        comm = iniData.commentProvided()
        if comm :
            self.add_comment(comm)
    # end of __init__
            
    def setComplexFields(self, flag = 'true') :
        self.add_string(self.Header["complexity"] % flag)
                    
    def addSnapshot(self, props, time_step) :
        field = props['field']
        component = props['component']
        fname = field + component
        
        varName = 'transient%s' % self.countTransients
        self.addFunction(name = varName, body = self.Code['snapshot'] % (fname, time_step, field, component))
        self.lineTransCode += " " + varName
        self.countTransients += 1
        
    def addLocalSnapshot(self, props, time_step) :
        field = props['field']
        component = props['component']
        fname = field + component + '-loc-%s' % self.countTransients
        
        pos_x = props['position']['x']
        pos_y = props['position']['y']
    
        varName = 'transient%s' % self.countTransients
        self.addFunction(name = varName, body = self.Code['field_local'] % \
                         (fname, time_step, pos_x, pos_y, field, component))
        self.lineTransCode += " " + varName
        self.countTransients += 1
                
    def add_string(self, add_str) :
        self.bufStr = add_str
        self.push()
        
    def push(self) :
        self.buffer.append(self.bufStr)
        self.bufStr = ""
        
    def add_comment(self, add_str) :
        self.add_string("; " + add_str)
        
    def form_line(self, add_str) :
        # adds a piece to the current line
        self.bufStr += add_str
        
    def dump(self):
        print("The output is written to: ", self.FileName)
        try:
            with open(self.FileName, "w") as ctlFile :
                for str in self.buffer :
                    ctlFile.write(str + "\n")
        except IOError :
            # TODO: raise proper exceptions
            print("Couldn't open ctl file")
            raise

    def defineGeneralArea(self, size_x, size_y, size_z) :
        if size_z == None :
            size_z = 'no-size'
        self.add_string(self.Code["geometry"] %(size_x, size_y, size_z))
    
    def startGeometry(self) :
        self.add_string(self.Code["geometry_head"])
        
    def finalizeGeometry(self):
        self.add_string(self.Code["geometry_tail"])
    
    def startSources(self) :
        self.add_string(self.Code["sources_head"])

    def finalizeSources(self) :
        self.add_string(self.Code["sources_tail"])

    def addblock(self, medium, xL, xR, yB, yT, zB, zT) :
        # adds the piece of code corresponding to the block made of medium
        # TODO: if medium is not understood, raise an exception
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB 
        centY = yB + sizeY/2.0
        sizeZ = abs(zT - zB)
        
        if sizeZ < Tolerance: 
            sizeZ = 'infinity'
    
        self.form_line(self.Code["block_head"])
    
        str = self.Code["block_position"] % (centX, centY, sizeX, sizeY, sizeZ)    
        self.form_line(str)
    
        if medium["medium"] == "metal" :
            str = self.Code["block_metal"] % (medium["epsilon"], medium["conductivity"])
        else :
            # dielectric
            str = self.Code["block_dielectric"] % medium["epsilon"]
    
        self.form_line(str)
        self.form_line(self.Code["block_tail"])
        self.push()

    def addsource(self, props, xL, xR, yB, yT, zB, zT) :
        # adds the source 
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB 
        centY = yB + sizeY/2.0
        sizeZ = abs(zT - zB)
        if sizeZ < Tolerance :
            sizeZ = 'infinity'
    
        self.form_line(self.Code["source_head"])
    
        self.form_line(self.Code['source_component'] % props['component'])
        self.form_line(self.Code["source_position"] % (centX, centY, sizeX, sizeY, sizeZ)    )
    
        if props["type"] == "pulse" :
            str = self.Code["source_types"]["pulse"] % (props["center"], props["width"])
        else :
            str = self.Code["source_types"]["continuous"] % (props["center"], props["width"])
    
        self.form_line(str)
        self.form_line(self.Code["source_tail"])
        self.push()
        
    def addPML(self):
        self.add_string(self.Code["pml"])
        
    def addresolution(self, res) :
        self.add_string(self.Code["resolution"] % res)
        
    def addFunction(self, name, body) :
        self.form_line(self.Code['function_head'] % name)
        self.form_line("%s" % body)
        self.form_line(self.Code['function_tail'])
        self.push()
        
    def addflux(self, props, xL, xR, yB, yT, zB, zT) :
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB
        centY = yB + sizeY/2.0
        sizeZ = abs(zB - zT)
        if sizeZ < Tolerance :
            sizeZ = ''

        bodyFlux = (self.Code["flux_prop"] % (props["center"], props["width"], props["resolution"])) + \
            (self.Code["flux_position"] % (centX, centY, sizeX, sizeY, sizeZ)) + ')'
        varName = 'trans%s' % self.countFluxPoints
        self.addFunction(name = varName, body = bodyFlux)

        self.lineFluxCode += " " + varName
        self.countFluxPoints += 1

    def finalizeFluxes(self):
        str = self.Code["fluxes_head"]
        str += self.lineFluxCode
        str += self.Code["fluxes_tail"]
        
        self.add_string(str)
    
    def startRunControl(self, property, **kwargs) : 
        # forms (run-* line 
        if property == 'decay':
            self.form_line(self.Code["time_decay"] % (kwargs['duration'], kwargs['pos_x'], kwargs['pos_y']))
        elif property == 'fixed' :
            self.form_line(self.Code["time_fixed"] % kwargs['duration'])
            
    def addRunControl(self, body = None) :
        if body == None :
            body = ""
            for num in range(self.countTransients) :
                body += " transient%s" % num
        self.form_line(" " + body)
            
    def endRunControl(self) :
        self.form_line(self.Code['time_tail'])
        self.push()

# end of class MeepControl and its Exceptions

def main(iniData, rcFileName) :
    """
    Accept classes containing initializing data 
    rcFileName - name of the resource file
    iniData - configuration of the structure (instance of ctlInfo).
    
    This function should work standalone as well as within a script.
    """    
    ctlFile = MeepControl(iniData.getCtlName(), rcFileName)
    contrData = iniData.getSection("Controls")
    
    # 0. Set whether fields should be regarded as complex or not
    
    if 'complex' in dict(contrData) and contrData['complex']:
        ctlFile.setComplexFields()

    # 1. Find the limiting points
    s = iniData.getSection("Geometry")["overshot"]
    
    if iniData.getNumElements() == 0 :
        print("Empty structure is generated")
        
        ctlFile.defineGeneralArea(2*s, 2*s, None if iniData.zSize <= 0 else iniData.zSize + 2*s)
    else :
        # [2015-2-11] We take the limiting coordinates strictly
        # We assume that incoming/outgoing channels enter MinX, MaxX planes only
        MinX, MaxX, MinY, MaxY, MinZ, MaxZ = iniData.colLines.getLimits()
        width = MaxX - MinX
        height = MaxY - MinY + 2*s
        zSize = MaxZ - MinZ
        if abs(zSize) < Tolerance :
            zSize = 0
        ctlFile.defineGeneralArea(width, height, None if iniData.zSize <= 0 else iniData.zSize + 2*s)
            
    # 2. We create a list of blocks corresponding to each line
    
    def add_flat(line, x1, x2) :
        # adds the flat part extending from x1 to x2
        # (for later) we think about x1 and x2 given in the local frame
        props = line['property']
        y = line['start']['y']
        # the up metal part
        yBottom = y + 0.5*props['width']
        yTop = y + line['weak_space_up']
        zBottom, zTop = -props['elevation'], props['elevation']
        ctlFile.addblock(props['materials']["up"], x1, x2, yBottom, yTop, zBottom, zTop)
        # the middle part
        yTop = yBottom
        yBottom = yTop - props["width"]
        ctlFile.addblock(props["materials"]["in"], x1, x2, yBottom, yTop, zBottom, zTop)
        # lower metallic part
        yTop = yBottom
        yBottom = y - line['weak_space_down']
        ctlFile.addblock(line_props["materials"]["down"], x1, x2, yBottom, yTop, zBottom, zTop)
    # end of add_flat
    
    def add_groove(line, x1, x2) :
        # adds the part corresponding to a grove 
        props = line['property']
        zBottom, zTop = -props['elevation'], props['elevation']
        
        y = line['start']['y']
        # the up metal part
        yBottom = y + 0.5*props['width']  + props['grooves']['depth']
        yTop = y + line['weak_space_up']
        ctlFile.addblock(props['materials']["up"], x1, x2, yBottom, yTop, zBottom, zTop)
        # the middle part
        yTop = yBottom
        yBottom = yTop - props["width"] - 2.0*props['grooves']['depth']
        ctlFile.addblock(props["materials"]["in"], x1, x2, yBottom, yTop, zBottom, zTop)        
        # lower metallic part
        yTop = yBottom
        yBottom = y - line['weak_space_down']
        ctlFile.addblock(line_props["materials"]["down"], x1, x2, yBottom, yTop, zBottom, zTop)        
    # end of add_groove
         
    ctlFile.startGeometry()
    for line in iniData.getLines() :
        comm = iniData.commentProvided(line)
        if comm :
            ctlFile.add_comment(comm)
            
        x1 = line["start"]["x"]
        # in what follows x1 denotes the cursor position
        x2 = line["end"]["x"]
        y1 = line["start"]["y"]
        y2 = line["end"]["y"]   
        
        print("Adding %s: (%s, %s)-(%s, %s)" % (line['type'], x1, y1, x2, y2))
        length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        # TODO: direction
        line_props = line['property']
        zBottom, zTop = -line_props['elevation'], line_props['elevation']
        
        if line['type'] == 'connector' :
            # this is three block system
            # top block
            xLeft = x1 - 0.5*line_props['width']
            xRight = x1 + 0.5*line_props['width']
            yBottom = y2
            
            reference = line['start']['attached_to']['property']
            yTop = y2 + reference['padding'] + reference['grooves']['depth']
            ctlFile.addblock(reference['materials']["up"], xLeft, xRight, yBottom, yTop, zBottom, zTop)
            
            # middle dielectric
            yTop = y2
            yBottom = y1
            ctlFile.addblock(line_props['materials']["in"], xLeft, xRight, yBottom, yTop, zBottom, zTop)
            
            # bottom 
            yTop = y1
            yBottom = y1 - reference['padding'] - reference['grooves']['depth']
            ctlFile.addblock(reference['materials']["up"], xLeft, xRight, yBottom, yTop, zBottom, zTop)
            
            # TODO: patches
            # if is not attached on side : side.cover(whole)
            # else: side.cover(whole - width_of_attached_lines)
            # if not end.attached (to another connector) : add_terminating_block
            
            continue # to avoid ridiculously long if-else
        
        period = float(line_props["grooves"]["period"])
        length_rest = length # ?? since == length - x1
        
        len_groove = line_props['grooves']['width']
        len_flat = period - len_groove
        
        # 1. Add an "incomplete" block due to initial skip of a part of the period
        # 2. Add proper periods
        # 3. Add possible "incomplete" block at the end
        len_start_left = period*(1 - line['start']['skip'])
        len_start_flat_left = len_start_left - len_groove
        
        if len_start_flat_left > 0 :
            if length_rest < len_start_flat_left :
                # we have a short line that doesn't cover the rest of the flat part
                add_flat(line, x1, x2)
                continue
            # at least the flat part is covered
            x2 = x1 + len_start_flat_left
            add_flat(line, x1, x2)
            len_start_left -= len_start_flat_left # == line_props['grooves']['width']
            x1 = x2
            length_rest -= len_start_flat_left
            # the cursor is at the beginning of the groove in the incomplete part
        # end adding starting flat part
        len_start_groove_left = len_start_left
        
        if length_rest < len_start_groove_left :
            x2 = x1 + length_rest
            add_groove(line, x1, x2)
            continue
        x2 = x1 + len_start_groove_left
        add_groove(line, x1, x2)
        x1 = x2
        length_rest -= len_start_groove_left
        # The starting part is done now to proper periods
        numperiods = int(length_rest/period)
        
        for part in range(numperiods) :
            x2 = x1 + len_flat
            add_flat(line, x1, x2)
            x1 = x2
            x2 = x1 + len_groove
            add_groove(line, x1, x2)
            x1 = x2
            length_rest -= period
        # loop over periods
        
        # Now we deal with the tail
        if length_rest > len_flat :
            x2 = x1 + len_flat
            add_flat(line, x1, x2)
            x1 = x2
            length_rest -= len_flat
            x2 = x1 + length_rest
            add_groove(line, x1, x2)
        else:
            x2 = x1 + length_rest
            add_flat(line, x1, x2)
    # end of loop over lines
        
    ctlFile.finalizeGeometry()
    
    # 3. Add sources
    ctlFile.startSources()
   
    for source in iniData.listSources:
        x1 = source["position"]["x"]
        x2 = x1
        y1 = source["position"]["y"] - source["position"]["width"]*0.5
        y2 = source["position"]["y"] + source["position"]["width"]*0.5
        
        z1 = -source['position']['elevation']
        z2 = source['position']['elevation']
        
        print("Adding source: (%s, %s, %s)" % (x1, y1, z1))
        
        comm = iniData.commentProvided(source)
        if comm :
            ctlFile.add_comment(comm)
            
        ctlFile.addsource(source["property"], x1, x2, y1, y2, z1, z2)
    
    ctlFile.finalizeSources()
    
    # 4. Add pml and resolution
    ctlFile.addPML()
    
    ctlFile.addresolution(contrData["resolution"])
    
    # 6. Define flux points
    # The procedure here is different because each flux region is a separate variable
    # They must be defined before the time control is defined
    
    count = 0
    for fluxp in iniData.listFluxPoints :
        print("Adding flux collector: %s at (%s, %s)" \
              % (count, fluxp['position']['x'], fluxp['position']['y']))
        count += 1
        
        x1 = fluxp["position"]["x"]
        x2 = x1
        y1 = fluxp["position"]["y"] - fluxp["position"]["width"]*0.5
        y2 = fluxp["position"]["y"] + fluxp["position"]["width"]*0.5
        z1 = -fluxp['position']['elevation']
        z2 = fluxp['position']['elevation']
        
        ctlFile.addflux(fluxp["property"], x1, x2, y1, y2, z1, z2)
        
    # 6.1. Add snapshots and other transient functions
    # TODO: reimplement this part to avoid unnecessary repetitions
    
    def setResolution(snap) :
        return 0.6 if not 'resolution' in dict(snap) else float(snap['resolution'])
    # end setResolution
    
    count = 0
    for transient in iniData.listTransients:
        print("Adding transient function: %s, type %s" % (count, transient))
        count += 1
        if "snapshot" in dict(transient) :
            snaps = transient['snapshot']
            res = setResolution(snaps)
            ctlFile.addSnapshot(snaps, res)
        elif 'field' in dict(transient) :
            snaps = transient['field']
            res = setResolution(snaps)
            ctlFile.addLocalSnapshot(snaps, res)

    # 7. Add Run control
    # 7.1 add run control
    if "structure_only" in dict(contrData['time']) and contrData['time']['structure_only']:
        ctlFile.startRunControl('fixed', duration = 0.1)
    elif contrData["time"]["type"] == "decay":
        if len(iniData.listFluxPoints) == 0 :
            # if no flux points are defined we take default at the center
            # TODO: look at other sort of positioned collectors if no flux points are defined
            cont_pos_x = 0
            cont_pos_y = 0
        else:
            # we take the position of the first flux point
            # TODO: read the position off the ini-file
            cont_pos_x = iniData.listFluxPoints[0]["position"]["x"]
            cont_pos_y = iniData.listFluxPoints[0]["position"]["y"]
        
        ctlFile.startRunControl("decay", duration = contrData["time"]["duration"], 
                                   pos_x = cont_pos_x, pos_y = cont_pos_y)
    elif contrData["time"]["type"] == "fixed":
        ctlFile.startRunControl("fixed", duration = contrData["time"]["duration"])
        
    # 7.2 add transient functions 
    # for transient in iniDdata.listTransientsFunctions ...
    ctlFile.addRunControl()
        
    ctlFile.endRunControl()

    # 8. Add output of flux points
    ctlFile.finalizeFluxes()

    ctlFile.dump()

if __name__ == "__main__" :
    
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', default = None, help = 'The resource file')
    parser.add_argument('-i', default = 'gen.ini', help = 'The meta-configuration file')
    args = parser.parse_args()

    rcFileName = args.r
    iniData = ctlInfo(args.i)
    
    # Poor man handling exceptions
    # TODO: introduce more elaborated treatment, since there may be different situations
        
    if not iniData.isValid :
        sys.exit("Configuration file is not found or doesn't describe a valid structure")

    main(iniData, rcFileName)
