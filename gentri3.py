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

import numpy as np
import copy # for copying nested dictionaries
import sys
import yaml
from datetime import datetime

import os

# *** Some general constants ***
# When a float is considered zero
Tolerance = 1e-6

class clYAML(object):
    # class dealing with YAML data
    isValid = False
    Data = None

    def validate(self) :
        # Here the trivial validation is performed
        #  
        return len(self.Data) > 0 and self.subvalidate()
    
    def subvalidate(self) :
        # For subclasses to do their stuff
        return True

    def __init__(self, FileName) :
        # TODO: deal with file problems better
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
    # Currently it does nothing
    
    def __init__(self, rcFileName = None) :
        # the constructor accepts the name of the resource file
        if rcFileName == None :
            # look for the .rc file in the directory where the py file resides
            script_path, _ = os.path.split(os.path.realpath(__file__))
            rcFileName = os.path.join(script_path, 'gen.rc')

        super(genResource, self).__init__(rcFileName)
        
## end of class genResource

### classes Line and CollectionLines

class collectionLines(object) :
    def __init__ (self, listLines = None) :
        self.listLines = []
        self.MinX = 0
        self.MaxX = 0
        self.MinY = 0
        self.MaxY = 0
        
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
        return self.MinX, self.MaxX, self.MinY, self.MaxY
        
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
            (curMinX, curMaxX) = (start['x'], end['x']) if start['x'] < end['x'] else (end['x'], start['x'])
            
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
            # The awkward second argument is to support the self-reference for the end point
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
        # end of isOverlap
        
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
    
    listSources = []
    listFluxPoints = []
    
    # comments on the content
    numWarnings = 0
    bufWarnings = []
    numErrors = 0
    bufErrors = []
    
    def subvalidate (self) :
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
    
            self.listSources.append(source["source"])
        # end of addsource
        
        def addObserver(obs) :
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
    
            self.listFluxPoints.append(obs["flux"])
        # end of addobserver

        # Here's the main code
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
            print("The elements are confined within (X: %s, %s) (Y: %s, %s)" 
                  % (self.colLines.MinX, self.colLines.MaxX, self.colLines.MinY, self.colLines.MaxY))
            
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
        for col in listElem :
            addObserver(col)
                
        return True
        
    def __init__(self, iniFileName = None) :
        self.colLines = collectionLines()
        super(ctlInfo, self).__init__("gen.ini" if iniFileName == None else iniFileName)
        self.topComment = self.getSection('comment')
        
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

## class ctlInfo and its Exceptions

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
        # accumulator of flux points
        self.listFluxPoints = []
        self.snapCodeLine = ""
        
        self.Code = self.rcData.getSection("Code")
        
        # write the header
        resources = self.rcData.getSection("Header")
        self.add_comment(resources["intro"])
        self.add_comment(resources['gendata']['header'] + datetime.now().strftime("%Y/%m/%d %H:%M"))
        self.add_comment(resources['gendata']["base"] + iniData.iniFileName)
        comm = iniData.commentProvided()
        if comm :
            self.add_comment(comm)
        
    def setSnapshot(self, component, time_step, field = 'e') :
        fname = field + component
        self.snapCodeLine = self.Code['snapshot'] % (fname, time_step, field, component)
        
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

    def defineGeneralArea(self, size_x, size_y) :
        self.add_string(self.Code["geometry"] %(size_x, size_y))
    
    def startGeometry(self) :
        self.add_string(self.Code["geometry_head"])
        
    def finalizeGeometry(self):
        self.add_string(self.Code["geometry_tail"])
    
    def startSources(self) :
        self.add_string(self.Code["sources_head"])

    def finalizeSources(self) :
        self.add_string(self.Code["sources_tail"])

    def addblock(self, medium, xL, xR, yB, yT) :
        # adds the piece of code corresponding to the block made of medium
        # TODO: if medium is not understood, raise an exception
        
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB 
        centY = yB + sizeY/2.0
    
        self.form_line(self.Code["block_head"])
    
        str = self.Code["block_position"] % (centX, centY, sizeX, sizeY)    
        self.form_line(str)
    
        if medium["medium"] == "metal" :
            str = self.Code["block_metal"] % (medium["epsilon"], medium["conductivity"])
        else :
            # dielectric
            str = self.Code["block_dielectric"] % medium["epsilon"]
    
        self.form_line(str)
        self.form_line(self.Code["block_tail"])
        self.push()

    def addsource(self, props, xL, xR, yB, yT) :
        # adds the source 
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB 
        centY = yB + sizeY/2.0
    
        self.form_line(self.Code["source_head"])
    
        self.form_line(self.Code['source_component'] % props['component'])
        self.form_line(self.Code["source_position"] % (centX, centY, sizeX, sizeY)    )
    
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
        
    def addflux(self, counter, props, xL, xR, yB, yT) :
        sizeX = xR - xL
        centX = xL + sizeX/2.0
        sizeY = yT - yB
        centY = yB + sizeY/2.0
    
        self.form_line(self.Code["flux_head"] % counter)
        self.form_line(self.Code["flux_prop"] % (props["center"], props["width"], props["resolution"]))
        self.form_line(self.Code["flux_position"] % (centX, centY, sizeX, sizeY))
        self.form_line(self.Code["flux_tail"])
        self.push()
        
        self.listFluxPoints.append(counter)
        
    def finalizeFluxes(self):
        str = self.Code["fluxes_head"]
        # The standard identificator is 'trans'
        for num in self.listFluxPoints:
            str += " trans%s" % num
        str += self.Code["fluxes_tail"]
        
        self.add_string(str)
    
    def addtimecontrol(self, property, **kwargs) : 
        if property == 'decay':
            self.add_string(self.Code["time_decay"] % (self.snapCodeLine, kwargs['duration'], kwargs['pos_x'], kwargs['pos_y']))
        elif property == 'fixed' :
            self.add_string(self.Code["time_fixed"] % (kwargs['duration'], self.snapCodeLine))
        
def main(iniData, rcFileName) :
    """
    Accept classes containing initializing data 
    rcFileName - name of the resource file
    iniData - configuration of the structure (instance of ctlInfo).
    
    This function should work standalone as well as within a script.
    """
    ctlFile = MeepControl(iniData.getSection("Output")["ctl_file"], rcFileName)
    
    # 1. Find the limiting points
    s = iniData.getSection("Geometry")["overshot"]
    if iniData.getNumElements() == 0 :
        print("Empty structure is generated")
        
        ctlFile.defineGeneralArea(2*s, 2*s)
    else :
        # [2015-2-11] We take the limiting coordinates strictly
        # We assume that incoming/outgoing channels enter MinX, MaxX planes only
        MinX, MaxX, MinY, MaxY = iniData.colLines.getLimits()
        width = MaxX - MinX
        height = MaxY - MinY + 2*s
        ctlFile.defineGeneralArea(width, height)
            
    # 2. We create a list of blocks corresponding to each line
    
    def add_flat(line, x1, x2) :
        # adds the flat part extending from x1 to x2
        # (for later) we think about x1 and x2 given in the local frame
        props = line['property']
        y = line['start']['y']
        # the up metal part
        yBottom = y + 0.5*props['width']
        yTop = y + line['weak_space_up']
        ctlFile.addblock(props['materials']["up"], x1, x2, yBottom, yTop)
        # the middle part
        yTop = yBottom
        yBottom = yTop - props["width"]
        ctlFile.addblock(props["materials"]["in"], x1, x2, yBottom, yTop)        
        # lower metallic part
        yTop = yBottom
        yBottom = y - line['weak_space_down']
        ctlFile.addblock(line_props["materials"]["down"], x1, x2, yBottom, yTop)        
    # end of add_flat
    
    def add_groove(line, x1, x2) :
        # adds the part corresponding to a grove 
        props = line['property']
        y = line['start']['y']
        # the up metal part
        yBottom = y + 0.5*props['width']  + props['grooves']['depth']
        yTop = y + line['weak_space_up']
        ctlFile.addblock(props['materials']["up"], x1, x2, yBottom, yTop)
        # the middle part
        yTop = yBottom
        yBottom = yTop - props["width"] - 2.0*props['grooves']['depth']
        ctlFile.addblock(props["materials"]["in"], x1, x2, yBottom, yTop)        
        # lower metallic part
        yTop = yBottom
        yBottom = y - line['weak_space_down']
        ctlFile.addblock(line_props["materials"]["down"], x1, x2, yBottom, yTop)        
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
        
        if line['type'] == 'connector' :
            # this is three block system
            # top block
            xLeft = x1 - 0.5*line_props['width']
            xRight = x1 + 0.5*line_props['width']
            yBottom = y2
            
            reference = line['start']['attached_to']['property']
            yTop = y2 + reference['padding'] + reference['grooves']['depth']
            ctlFile.addblock(reference['materials']["up"], xLeft, xRight, yBottom, yTop)
            
            # middle dielectric
            yTop = y2
            yBottom = y1
            ctlFile.addblock(line_props['materials']["in"], xLeft, xRight, yBottom, yTop)
            
            # bottom 
            yTop = y1
            yBottom = y1 - reference['padding'] - reference['grooves']['depth']
            ctlFile.addblock(reference['materials']["up"], xLeft, xRight, yBottom, yTop)
            
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
        
        print("Adding source: (%s, %s)" % (x1, y1))
        
        comm = iniData.commentProvided(source)
        if comm :
            ctlFile.add_comment(comm)
            
        ctlFile.addsource(source["property"], x1, x2, y1, y2)
    
    ctlFile.finalizeSources()
    
    # 4. Add pml and resolution
    ctlFile.addPML()
    
    contrData = iniData.getSection("Controls")
    
    ctlFile.addresolution(contrData["resolution"])
    
    # 6. Define flux points
    # The procedure here is different because each flux region is a separate variable
    # They must be defined before the time control is defined
    
    countFluxes = 0
    for fluxp in iniData.listFluxPoints :
        print("Adding flux collector: %s at (%s, %s)" % (countFluxes, fluxp['position']['x'], fluxp['position']['y'])) # fluxp
        
        x1 = fluxp["position"]["x"]
        x2 = x1
        y1 = fluxp["position"]["y"] - fluxp["position"]["width"]*0.5
        y2 = fluxp["position"]["y"] + fluxp["position"]["width"]*0.5
        
        ctlFile.addflux(countFluxes, fluxp["property"], x1, x2, y1, y2)        
        countFluxes += 1

    # 7. Add time control

    if "snapshot" in dict(contrData) :
        if 'resolution' in dict(contrData['snapshot']) :
            res = float(contrData['snapshot']['resolution'])
        else :
            res = 0.6
        ctlFile.setSnapshot(contrData['snapshot']['component'], res, contrData['snapshot']['field'])
    
    if "structure_only" in dict(contrData['time']) and contrData['time']['structure_only']:
        ctlFile.addtimecontrol('fixed', duration = 0.1)
    elif contrData["time"]["type"] == "decay":
        if len(iniData.listFluxPoints) == 0 :
            # if no flux points are defined we take default at the center
            cont_pos_x = 0
            cont_pos_y = 0
        else:
            # we take the position of the first flux point
            # TODO: read the position off the ini-file
            cont_pos_x = iniData.listFluxPoints[0]["position"]["x"]
            cont_pos_y = iniData.listFluxPoints[0]["position"]["y"]
        
        ctlFile.addtimecontrol("decay", duration = contrData["time"]["duration"], 
                                   pos_x = cont_pos_x, pos_y = cont_pos_y)
    elif contrData["time"]["type"] == "fixed":
        ctlFile.addtimecontrol("fixed", duration = contrData["time"]["duration"])        

    # 8. Add flux points
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
