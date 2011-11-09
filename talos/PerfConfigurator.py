#!/usr/bin/env python
# encoding: utf-8
"""
PerfConfigurator.py

Created by Rob Campbell on 2007-03-02.
Modified by Rob Campbell on 2007-05-30
Modified by Rob Campbell on 2007-06-26 - added -i buildid option
Modified by Rob Campbell on 2007-07-06 - added -d testDate option
Modified by Ben Hearsum on 2007-08-22 - bugfixes, cleanup, support for multiple platforms. Only works on Talos2
Modified by Alice Nodelman on 2008-04-30 - switch to using application.ini, handle different time stamp formats/options
Modified by Alice Nodelman on 2008-07-10 - added options for test selection, graph server configuration, nochrome
Modified by Benjamin Smedberg on 2009-02-27 - added option for symbols path
"""

import sys
import re
import time
from datetime import datetime
from os import path
import os
import optparse

defaultTitle = "qm-pxp01"

class PerfConfigurator:
    attributes = ['exePath', 'configPath', 'sampleConfig', 'outputName', 'title',
                  'branch', 'branchName', 'buildid', 'currentDate', 'browserWait',
                  'verbose', 'testDate', 'useId', 'resultsServer', 'resultsLink',
                  'activeTests', 'noChrome', 'fast', 'testPrefix', 'extension',
                  'masterIniSubpath', 'test_timeout', 'symbolsPath', 'addonID', 
                  'noShutdown', 'extraPrefs', 'xperf_path', 'mozAfterPaint', 
                  'webServer', 'develop'];
    masterIniSubpath = "application.ini"

    def _dumpConfiguration(self):
        """dump class configuration for convenient pickup or perusal"""
        print "Writing configuration:"
        for i in self.attributes:
            print " - %s = %s" % (i, getattr(self, i))
    
    def _getCurrentDateString(self):
        """collect a date string to be used in naming the created config file"""
        currentDateTime = datetime.now()
        return currentDateTime.strftime("%Y%m%d_%H%M")

    def _getMasterIniContents(self):
        """ Open and read the application.ini from the application directory """
        master = open(path.join(path.dirname(self.exePath), self.masterIniSubpath))
            
        data = master.read()
        master.close()
        return data.split('\n')
    
    def _getCurrentBuildId(self):
        masterContents = self._getMasterIniContents()
        if not masterContents:
            raise Configuration("Could not get BuildID: master ini file empty or does not exist")

        reBuildid = re.compile('BuildID\s*=\s*(\d{10}|\d{12})')
        for line in masterContents:
            match = re.match(reBuildid, line)
            if match:
                return match.group(1)
        raise Configuration("BuildID not found in " 
          + path.join(path.dirname(self.exePath), self.masterIniSubpath))
    
    def _getTimeFromTimeStamp(self):
        if len(self.testDate) == 14: 
          buildIdTime = time.strptime(self.testDate, "%Y%m%d%H%M%S")
        elif len(self.testDate) == 12: 
          buildIdTime = time.strptime(self.testDate, "%Y%m%d%H%M")
        else:
          buildIdTime = time.strptime(self.testDate, "%Y%m%d%H")
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", buildIdTime)

    def _getTimeFromBuildId(self):
        if len(self.buildid) == 14: 
          buildIdTime = time.strptime(self.buildid, "%Y%m%d%H%M%S")
        elif len(self.buildid) == 12: 
          buildIdTime = time.strptime(self.buildid, "%Y%m%d%H%M")
        else:
          buildIdTime = time.strptime(self.buildid, "%Y%m%d%H")
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", buildIdTime)

    def convertLine(self, line, testMode, printMe):
        buildidString = "'" + str(self.buildid) + "'"
        activeList = self.activeTests.split(':')
        newline = line
        if 'test_timeout:' in line:
            newline = 'test_timeout: ' + str(self.test_timeout) + '\n'
        if 'browser_path:' in line:
            newline = 'browser_path: ' + self.exePath + '\n'
        if 'xperf_path:' in line:
            newline = 'xperf_path: %s\n' % self.xperf_path
        if 'browser_log:' in line:
            newline = 'browser_log: ' + self.logFile + '\n'
        if 'webserver:' in line:
           newline = 'webserver: %s\n' % self.webServer
        if 'title:' in line:
            newline = 'title: ' + self.title + '\n'
            if self.testDate:
                newline += '\n'
                newline += 'testdate: "%s"\n' % self._getTimeFromTimeStamp()
            elif self.useId:
                newline += '\n'
                newline += 'testdate: "%s"\n' % self._getTimeFromBuildId()
            if self.addonID:
                newline += '\n'
                newline += 'addon_id: "%s"\n' % self.addonID
            if self.branchName: 
                newline += '\n'
                newline += 'branch_name: %s\n' % self.branchName
            if self.noChrome and not self.mozAfterPaint:
                newline += '\n'
                newline += "test_name_extension: _nochrome\n"
            elif self.noChrome and self.mozAfterPaint:
                newline += '\n'
                newline += "test_name_extension: _nochrome_paint\n"
            elif not self.noChrome and self.mozAfterPaint:
                newline += '\n'
                newline += "test_name_extension: _paint\n"

            if self.symbolsPath:
                newline += '\nsymbols_path: %s\n' % self.symbolsPath
        if self.extension and ('extensions : {}' in line):
            newline = 'extensions: ' + '\n- ' + self.extension
        if 'buildid:' in line:
            newline = 'buildid: %s\n' % buildidString
        if 'talos.logfile:' in line:
            parts = line.split(':')
            if (parts[1] != None and parts[1].strip() == ''):
                lfile = os.path.join(os.getcwd(), 'browser_output.txt')
            else:
                lfile = parts[1].strip().strip("'")
                lfile = os.path.abspath(lfile)

            lfile = lfile.replace('\\', '\\\\')
            newline = '%s: %s\n' % (parts[0], lfile)
        if 'testbranch' in line:
            newline = 'branch: ' + self.branch

        #only change the results_server if the user has provided one
        if 'develop' in line:
            newline = 'develop: %s\n' % self.develop
        if self.resultsServer and ('results_server' in line):
            newline = 'results_server: ' + self.resultsServer + '\n'
        #only change the results_link if the user has provided one
        if self.resultsLink and ('results_link' in line):
            newline = 'results_link: ' + self.resultsLink + '\n'
        #only change the browser_wait if the user has provided one
        if self.browserWait and ('browser_wait' in line):
            newline = 'browser_wait: ' + str(self.browserWait) + '\n'
        if self.noShutdown and ('shutdown :' in line):
            newline = line.replace('True', 'False')
        if 'init_url' in line:
            newline = self.convertUrlToRemote(newline)
        if testMode:
            if ('url' in line) and ('url_mod' not in line):
                newline = self.convertUrlToRemote(newline)
                line = newline

            #only do this if the user has provided a list of tests to turn on/off
            # otherwise, all tests are considered to be active
            if self.activeTests:
                if line.startswith('- name'): 
                    #found the start of an individual test description
                    printMe = False
                for test in activeList: 
                    reTestMatch = re.compile('^-\s*name\s*:\s*' + test + '\s*$')
                    #determine if this is a test we are going to run
                    match = re.match(reTestMatch, line)
                    if match:
                        printMe = True
                        if (test == 'tp') and self.fast: #only affects the tp test name
                            newline = newline.replace('tp', 'tp_fast')
                        if self.testPrefix:
                            newline = newline.replace(test, self.testPrefix + '_' + test)

            #HACK: we are depending on -tpchrome to be in the cli options in order to run mozafterpaint
            if self.mozAfterPaint and (line.find('-tpchrome') > 0): 
                #if mozAfterPaint is True add -tpmozafterpaint option 
                line = line.replace('-tpchrome ','-tpchrome -tpmozafterpaint ')
                newline = line

            if self.noChrome: 
                #if noChrome is True remove --tpchrome option 
                newline = line.replace('-tpchrome ','')

        if self.extraPrefs != [] and (re.match('^\s*preferences :\s*$', line)): 
            newline = 'preferences :\n'
            for v in self.extraPrefs:
                thispref = v.split("=")
                if len(thispref) < 2:
                    print "Error: syntax error in --setPref=" + v
                    sys.exit(1)
                newline += '  %s: %s\n' % (thispref[0], thispref[1])
            
        return printMe, newline

    def writeConfigFile(self):
        try:
            configFile = open(path.join(self.configPath, self.sampleConfig))
        except:
            raise Configuration("unable to find %s, please check your filename for --sampleConfig" % path.join(self.configPath, self.sampleConfig))

        if (self.mozAfterPaint):
            found = False
            for p in self.extraPrefs: 
                if p[0] == 'dom.send_after_paint_to_content':
                    found = True
            if not found:
                self.extraPrefs.append('dom.send_after_paint_to_content=true')

        destination = open(self.outputName, "w")
        config = configFile.readlines()
        configFile.close()
        printMe = True
        testMode = False
        for line in config:
            printMe, newline = self.convertLine(line, testMode, printMe)
            if printMe:
                destination.write(newline)
            if line.startswith('tests :'): 
                #enter into test writing mode
                testMode = True
                if self.activeTests:
                    printMe = False
        destination.close()
        if self.verbose:
            self._dumpConfiguration()
    
    def convertUrlToRemote(self, line):
        """
          For a give url line in the .config file, add a webserver.
          In addition if there is a .manifest file specified, covert 
          and copy that file to the remote device.
        """
        
        if (not self.webServer or self.webServer == 'localhost'):
          return line
        
        #NOTE: line.split() causes this to fail because it splits on the \n and not every single ' '
        parts = line.split(' ')
        newline = ''
        for part in parts:
            if '.html' in part:
                newline += 'http://' + self.webServer + '/' + part
            elif '.manifest' in part:
                newline += self.buildRemoteManifest(part) + ' '
            elif '.xul' in part:
                newline += 'http://' + self.webServer + '/' + part
            else:
                newline += part
                if (part <> parts[-1]):
                    newline += ' '

        return newline

    def buildRemoteManifest(self, manifestName):
        """
          Take a given manifest name, convert the localhost->remoteserver, and then copy to the device
          returns the remote filename on the device so we can add it to the .config file
        """
        fHandle = None
        try:
          fHandle = open(manifestName, 'r')
          manifestData = fHandle.read()
          fHandle.close()
        except:
          if fHandle:
            fHandle.close()
          return manifestName

        newHandle = open(manifestName + '.develop', 'w')
        for line in manifestData.split('\n'):
            newHandle.write(line.replace('localhost', self.webServer) + "\n")
        newHandle.close()
        
        return manifestName + '.develop'

    def __init__(self, options):
        self.__dict__.update(options.__dict__)

        self.currentDate = self._getCurrentDateString()
        if not self.buildid:
            self.buildid = self._getCurrentBuildId()
        if not self.outputName:
            self.outputName = self.currentDate + "_config.yml"

class Configuration(Exception):
    def __init__(self, msg):
        self.msg = "ERROR: " + msg

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

class TalosOptions(optparse.OptionParser):
    """Parses Mochitest commandline options."""
    def __init__(self, **kwargs):
        optparse.OptionParser.__init__(self, **kwargs)
        defaults = {}

        self.add_option("-v", "--verbose",
                        action = "store_true", dest = "verbose",
                        help = "display verbose output")
        defaults["verbose"] = False
    
        self.add_option("-e", "--executablePath",
                        action = "store", dest = "exePath",
                        help = "path to executable we are testing")
        defaults["exePath"] = ''
    
        self.add_option("-c", "--configPath",
                        action = "store", dest = "configPath",
                        help = "path to config file")
        defaults["configPath"] = ''

        self.add_option("-f", "--sampleConfig",
                        action = "store", dest = "sampleConfig",
                        help = "Input config file")
        defaults["sampleConfig"] = 'sample.config'

        self.add_option("-t", "--title",
                        action = "store", dest = "title",
                        help = "Title of the test run")
        defaults["title"] = defaultTitle
    
        self.add_option("--branchName",
                        action = "store", dest = "branchName",
                        help = "Name of the branch we are testing on")
        defaults["branchName"] = ''

        self.add_option("-b", "--branch",
                        action = "store", dest = "branch",
                        help = "Product branch we are testing on")
        defaults["branch"] = ''

        self.add_option("-o", "--output",
                        action = "store", dest = "outputName",
                        help = "Output file")
        defaults["outputName"] = ''

        self.add_option("-i", "--id",
                        action = "store_true", dest = "buildid",
                        help = "Build ID of the product we are testing")
        defaults["buildid"] = ''

        self.add_option("-u", "--useId",
                        action = "store", dest = "useId",
                        help = "Use the buildid as the testdate")
        defaults["useId"] = False

        self.add_option("-d", "--testDate",
                        action = "store", dest = "testDate",
                        help = "Test date for the test run")
        defaults["testDate"] = ''

        self.add_option("-w", "--browserWait",
                        action = "store", type="int", dest = "browserWait",
                        help = "Amount of time allowed for the browser to cleanly close")
        defaults["browserWait"] = 5

        self.add_option("-s", "--resultsServer",
                        action = "store", dest = "resultsServer",
                        help = "Address of the results server")
        defaults["resultsServer"] = ''
    
        self.add_option("-l", "--resultsLink",
                        action = "store", dest = "resultsLink",
                        help = "Link to the results from this test run")
        defaults["resultsLink"] = ''

        self.add_option("-a", "--activeTests",
                        action = "store", dest = "activeTests",
                        help = "List of tests to run, separated by ':' (ex. ts:tp4:tsvg)")
        defaults["activeTests"] = ''

        self.add_option("-n", "--noChrome",
                        action = "store_true", dest = "noChrome",
                        help = "do not run tests as chrome")
        defaults["noChrome"] = False

        self.add_option("--mozAfterPaint",
                        action = "store_true", dest = "mozAfterPaint",
                        help = "wait for MozAfterPaint event before recording the time")
        defaults["mozAfterPaint"] = False

        self.add_option("--testPrefix",
                        action = "store", dest = "testPrefix",
                        help = "the prefix for the test we are running")
        defaults["testPrefix"] = ''

        self.add_option("--extension",
                        action = "store", dest = "extension",
                        help = "Extension to install while running")
        defaults["extension"] = ''
    
        self.add_option("--fast",
                        action = "store_true", dest = "fast",
                        help = "Run tp tests as tp_fast")
        defaults["fast"] = False
    
        self.add_option("--symbolsPath",
                        action = "store", dest = "symbolsPath",
                        help = "Path to the symbols for the build we are testing")
        defaults["symbolsPath"] = ''

        self.add_option("--xperf_path",
                        action = "store", dest = "xperf_path",
                        help = "Path to windows performance tool xperf.exe")
        defaults["xperf_path"] = ''

        self.add_option("--test_timeout",
                        action = "store", type="int", dest = "test_timeout",
                        help = "Time to wait for the browser to output to the log file")
        defaults["test_timeout"] = 1200

        self.add_option("--logFile",
                        action = "store", dest = "logFile",
                        help = "Local logfile to store the output from the browser in")
        defaults["logFile"] = "browser_output.txt"
        self.add_option("--addonID",
                        action = "store", dest = "addonID",
                        help = "ID of the extension being tested")
        defaults["addonID"] = ''
        self.add_option("--noShutdown",
                        action = "store_true", dest = "noShutdown",
                        help = "Record time browser takes to shutdown after testing")
        defaults["noShutdown"] = False

        self.add_option("--setPref",
                        action = "append", type = "string",
                        dest = "extraPrefs", metavar = "PREF=VALUE",
                        help = "defines an extra user preference")  
        defaults["extraPrefs"] = []

        self.add_option("--webServer", action="store",
                    type = "string", dest = "webServer",
                    help = "IP address of the webserver hosting the talos files")
        defaults["webServer"] = ''

        self.add_option("--develop",
                        action = "store_true", dest = "develop",
                        help = "useful for running tests on a developer machine. \
                                Creates a local webserver and doesn't upload to the graph servers.")  
        defaults["develop"] = False

        self.set_defaults(**defaults)

    def verifyCommandLine(self, args, options):
        if len(args) > 0:
            raise Configuration("Configurator does not take command line arguments, only options (arguments were: %s)" % (",".join(args)))

        if options.develop == True:
            if  options.resultsServer == '':
                options.resultsServer = ' '
            if options.resultsLink == '':
                options.resultsLink = ' '
            
            if options.webServer == '':
              options.webServer = "localhost:%s" % (findOpenPort('127.0.0.1'))
        return options

# Used for the --develop option where we dynamically create a webserver
def getLanIp():
    import devicemanager
    nettools = devicemanager.NetworkTools()
    ip = nettools.getLanIp()
    port = findOpenPort(ip)
    return "%s:%s" % (ip, port)
    
def findOpenPort(ip):
    import devicemanager
    nettools = devicemanager.NetworkTools()
    port = nettools.findOpenPort(ip, 15707)
    return str(port)

def main(argv=None):
    parser = TalosOptions()
    options, args = parser.parse_args()

    progname = sys.argv[0].split("/")[-1]
    try:
        parser.verifyCommandLine(args, options)
        configurator = PerfConfigurator(options);
        configurator.writeConfigFile()
    except Configuration, err:
        print >> sys.stderr, progname + ": " + str(err.msg)
        return 4
    except EnvironmentError, err:
        print >> sys.stderr, "%s: %s" % (progname, err)
        return 4
    # Note there is no "default" exception handler: we *want* a big ugly
    # traceback and not a generic error if something happens that we didn't
    # anticipate

    return 0


if __name__ == "__main__":
    sys.exit(main())

