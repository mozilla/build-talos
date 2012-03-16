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

import filter
import sys
import re
import time
import os
import optparse
import utils
from datetime import datetime
from os import path

here = path.dirname(path.abspath(__file__))
defaultTitle = "qm-pxp01"

class Configuration(Exception):
    def __init__(self, msg):
        self.msg = "ERROR: " + msg


class PerfConfigurator(object):

    masterIniSubpath = "application.ini"

    # items that can be simply replaced on output
    replacements = ['test_timeout', 'browser_path', 'xperf_path', 'browser_log', 'webserver', 'buildid', 'develop', 'ignore_first']

    def __init__(self, **options):
        self.__dict__.update(options)

        self.deviceroot = options.get('deviceroot') # for tpmanifest interpolation
        # XXX this is here because convertLine is monolithic
        # so we proscribe the behaviour according to the subclass here.
        # If instead we made the parser more flexible then instead
        # remotePerfConfigurator could sensibly override this
        # behaviour without having to touch PerfConfigurator

        # use attributes from the options dict
        self.attributes = options.keys() + ['currentDate', 'masterIniSubpath']

        self.currentDate = self._getCurrentDateString()
        if not self.buildid:
            self.buildid = self._getCurrentBuildId()
        if not self.outputName:
            self.outputName = self.currentDate + "_config.yml"

        # ensure all preferences are of length 2 (preference, value)
        badPrefs = [i for i in self.extraPrefs if len(i) != 2]
        if badPrefs:
            raise Configuration("Prefs should be of length 2: %s" % badPrefs)


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
        master = open(path.join(path.dirname(self.browser_path), self.masterIniSubpath))
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
          + path.join(path.dirname(self.browser_path), self.masterIniSubpath))

    def _getTime(self, timestamp):
        if len(timestamp) == 14:
          buildIdTime = time.strptime(timestamp, "%Y%m%d%H%M%S")
        elif len(timestamp) == 12:
          buildIdTime = time.strptime(timestamp, "%Y%m%d%H%M")
        else:
          buildIdTime = time.strptime(timestamp, "%Y%m%d%H")
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", buildIdTime)

    def _getTimeFromTimeStamp(self):
        return self._getTime(self.testDate)

    def _getTimeFromBuildId(self):
        return self._getTime(self.buildid)

    def convertLine(self, line, testMode, printMe):
        """
        given a line in the sample config file convert this to an output
        line or lines in the output .yml file
        """
        # XXX This is not really much of a parser,
        # more like an elaborate version of sed
        # The tokens sought must be in the .config file or parsing will fail
        # Several tokens, such as `extensions: []`, `filters: []`
        # exist and are required to exist in the source .config files
        # for the sake of parsing.  We are also very whitespace sensitive.
        # https://bugzilla.mozilla.org/show_bug.cgi?id=725097
        # should fix this.

        # testmode == writing out a subset of talos tests
        if testMode:
            if line.startswith('- name'):
                # found the start of an individual test description
                printMe = False

                for test in self.activeTests.split(':'):
                    # determine if this is a test we are going to run
                    if re.match('^-\s*name\s*:\s*' + test + '\s*$', line):
                        printMe = True
                        if test == 'tp' and self.fast: #only affects the tp test name
                            line = line.replace('tp', 'tp_fast')
                            if self.testPrefix:
                                line = line.replace(test, '_'.join([self.testPrefix,
                                                                    test]))
                        if self.responsiveness:
                            line += "  responsiveness: True\n"

                        if self.noShutdown:
                            line += "  shutdown : True\n"

                        if self.noChrome:
                            line += "  tpchrome: False\n"

                        if self.mozAfterPaint:
                            line += "  tpmozafterpaint: True\n"

                        if self.tpcycles:
                            line = "  tpcycles: %s\n" % self.tpcycles

                        if self.tppagecycles:
                            line = "  tppagecycles: %s\n" % self.tppagecycles

                        if self.rss:
                            line += "  rss: True\n"

                        if self.tpdelay:
                            line += "  tpdelay: %s\n" % self.tpdelay

            elif printMe:
                if 'url' in line and 'url_mod' not in line:
                    line = self.convertUrlToRemote(line)

                if self.responsiveness and 'responsiveness' in line:
                    line = ""

                if self.noShutdown and 'shutdown :' in line:
                    line = ""

                if self.tpcycles and 'tpcycles' in line:
                    line = ""

                if "tpmanifest:" in line:
                    if self.tpmanifest:
                        line = "  tpmanifest: %s\n" % self.tpmanifest

                    # if --develop flag specified, generate .develop manifest
                    # and change manifest name in generated config file
                    if self.develop or self.deviceroot:
                        manifest = line.split(":")[1].strip()
                        if manifest:
                            line = "  tpmanifest: %s\n" % self.buildRemoteManifest(utils.interpolatePath(manifest))

            return printMe, line

        def writeList(thelist):
            """write a list in YAML"""
            return '\n'.join([(' - %s' % item) for item in thelist])

        newline = line

        if 'title:' in line:
            # write title block
            newline = 'title: ' + self.title + '\n'
            if self.testdate:
                newline += '\n'
                newline += 'testdate: "%s"\n' % self._getTimeFromTimeStamp()
            elif self.useId:
                newline += '\n'
                newline += 'testdate: "%s"\n' % self._getTimeFromBuildId()
            if self.addon_id:
                newline += '\n'
                newline += 'addon_id: "%s"\n' % self.addon_id
            if self.branch_name:
                newline += '\n'
                newline += 'branch_name: %s\n' % self.branch_name
            if self.noChrome or self.mozAfterPaint:
                newline += '\n'
                newline += "test_name_extension: "
                if self.noChrome:
                    newline += '_nochrome'
                if self.mozAfterPaint:
                    newline += '_paint'
                newline += '\n'

            if self.symbols_path:
                newline += '\nsymbols_path: %s\n' % self.symbols_path

        for item in self.replacements:
            if ('%s:' % item) in line:
                newline = '%s: %s\n' % (item, getattr(self, item))

        if self.extensions and ('extensions: []' in line):
            newline = 'extensions:\n%s\n' % writeList(self.extensions)

        if self.filters and ('filters:' in line):
            newline = 'filters:\n%s\n' % writeList(self.filters)

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

        #only change the results_url if the user has provided one
        if self.results_url and ('results_url' in line):
            newline = 'results_url: %s\n' % (self.results_url)
        #only change the browser_wait if the user has provided one
        if self.browser_wait and ('browser_wait' in line):
            newline = 'browser_wait: ' + str(self.browser_wait) + '\n'
        if 'init_url' in line:
            newline = self.convertUrlToRemote(newline)

        if self.extraPrefs and re.match('^\s*preferences:\s*$', line):
            newline = 'preferences:\n'
            for pref, value in self.extraPrefs:
                newline += '  %s: %s\n' % (pref, value)

        return printMe, newline

    def writeConfigFile(self):

        # read the config file
        try:
            configFile = open(path.join(self.configPath, self.sampleConfig))
        except:
            raise Configuration("unable to find %s, please check your filename for --sampleConfig" % path.join(self.configPath, self.sampleConfig))
        config = configFile.readlines()
        configFile.close()

        # fix up the preferences
        requiredPrefs = []
        if self.mozAfterPaint:
            requiredPrefs.append(('dom.send_after_paint_to_content', 'true'))
        if self.extensions:
            # enable the extensions;
            # see https://developer.mozilla.org/en/Installing_extensions
            requiredPrefs.extend([('extensions.enabledScopes', 5),
                                  ('extensions.autoDisableScopes', 10)])
        for pref, value in requiredPrefs:
            if not pref in [i for i, j in self.extraPrefs]:
                self.extraPrefs.append([pref, value])

        # write the config file
        destination = open(self.outputName, "w")
        printMe = True
        testMode = False
        for line in config:
            printMe, newline = self.convertLine(line, testMode, printMe)
            if printMe:
                destination.write(newline)
            if line.startswith('tests :'):
                #enter into test writing mode
                testMode = True
                printMe = False
        destination.close()

        # print the config file to stdout
        if self.verbose:
            self._dumpConfiguration()

    def convertUrlToRemote(self, line):
        """
          For a give url line in the .config file, add a webserver.
          In addition if there is a .manifest file specified, covert
          and copy that file to the remote device.
        """

        if (not self.webserver or self.webserver == 'localhost'):
          return line

        #NOTE: line.split() causes this to fail because it splits on the \n and not every single ' '
        parts = line.split(' ')
        newline = ''

        # We cannot load .xul remotely and winopen.xul is the only instance.
        # winopen.xul is handled in remotePerfConfigurator.py
        for part in parts:
            if '.html' in part:
                newline += 'http://' + self.webserver + '/' + part
            else:
                newline += part
                if part != parts[-1]:
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
          manifestLines = fHandle.readlines()
          fHandle.close()
        except:
          if fHandle:
            fHandle.close()
          raise # reraise current exception; prints traceback to screen

        newHandle = open(manifestName + '.develop', 'w')
        for line in manifestLines:
            newHandle.write(line.replace('localhost', self.webserver))
        newHandle.close()

        return manifestName + '.develop'


class TalosOptions(optparse.OptionParser):
    """Parses Talos commandline options."""

    class TalosOption(optparse.Option):
        def take_action(self, action, dest, opt, value, values, parser):
            """add the parsed option to the set of things parsed"""
            optparse.Option.take_action(self, action, dest, opt, value, values, parser)
            parser.parsed.add(dest)

    def __init__(self, **kwargs):
        kwargs['option_class'] = self.TalosOption
        optparse.OptionParser.__init__(self, **kwargs)
        self.parsed = set() # parsed arguments
        defaults = {}

        self.add_option("-v", "--verbose",
                        action="store_true", dest = "verbose",
                        help = "display verbose output")
        defaults["verbose"] = False

        self.add_option("-e", "--executablePath",
                        action = "store", dest = "browser_path",
                        help = "path to executable we are testing")
        defaults["browser_path"] = ''

        self.add_option("-c", "--configPath",
                        action = "store", dest = "configPath",
                        help = "path to config file")
        defaults["configPath"] = ''

        self.add_option("-f", "--sampleConfig",
                        action = "store", dest = "sampleConfig",
                        help = "Input config file")
        defaults["sampleConfig"] = os.path.join(here, 'sample.config')

        self.add_option("-t", "--title",
                        action = "store", dest = "title",
                        help = "Title of the test run")
        defaults["title"] = defaultTitle

        self.add_option("--branchName",
                        action = "store", dest = "branch_name",
                        help = "Name of the branch we are testing on")
        defaults["branch_name"] = ''

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

        self.add_option("--testDate",
                        action = "store", dest = "testdate",
                        help = "Test date for the test run")
        defaults["testdate"] = ''

        self.add_option("-w", "--browserWait",
                        action = "store", type="int", dest = "browser_wait",
                        help = "Amount of time allowed for the browser to cleanly close")
        defaults["browser_wait"] = 5

        self.add_option("--resultsServer",
                        action="store", dest="resultsServer",
                        help="Address of the results server [DEPRECATED: use --resultsURL]")
        defaults["resultsServer"] = ''

        self.add_option("-l", "--resultsLink",
                        action="store", dest="resultsLink",
                        help="Link to the results from this test run [DEPRECATED: use --resultsURL]")
        defaults["resultsLink"] = ''

        self.add_option("--results_url", dest="results_url",
                        help="URL of results server")
        defaults["results_url"] = ''

        self.add_option("-a", "--activeTests",
                        action = "store", dest = "activeTests",
                        help = "List of tests to run, separated by ':' (ex. ts:tp4:tsvg)")
        defaults["activeTests"] = ''

        self.add_option("--noChrome",
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

        self.add_option("--extension", dest="extensions", action="append",
                        help="Extension to install while running [DEFAULT: %default]")
        defaults["extensions"] = []

        self.add_option("--fast",
                        action = "store_true", dest = "fast",
                        help = "Run tp tests as tp_fast")
        defaults["fast"] = False

        self.add_option("--symbolsPath",
                        action = "store", dest = "symbols_path",
                        help = "Path to the symbols for the build we are testing")
        defaults["symbols_path"] = ''

        self.add_option("--xperf_path",
                        action = "store", dest = "xperf_path",
                        help = "Path to windows performance tool xperf.exe")
        defaults["xperf_path"] = ''

        self.add_option("--test_timeout",
                        action = "store", type="int", dest = "test_timeout",
                        help = "Time to wait for the browser to output to the log file")
        defaults["test_timeout"] = 1200

        self.add_option("--logFile",
                        action = "store", dest = "browser_log",
                        help = "Local logfile to store the output from the browser in")
        defaults["browser_log"] = "browser_output.txt"
        self.add_option("--addonID",
                        action = "store", dest = "addon_id",
                        help = "ID of the extension being tested")
        defaults["addon_id"] = ''
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
                    type = "string", dest = "webserver",
                    help = "IP address of the webserver hosting the talos files")
        defaults["webserver"] = ''

        self.add_option("--develop",
                        action="store_true", dest="develop",
                        help="useful for running tests on a developer machine. \
                                Creates a local webserver and doesn't upload to the graph servers.")
        defaults["develop"] = False

        self.add_option("--responsiveness",
                        action = "store_true", dest = "responsiveness",
                        help = "turn on responsiveness collection")
        defaults["responsiveness"] = False

        self.add_option("--rss",
                        action = "store_true", dest = "rss",
                        help = "Collect RSS counters from pageloader instead of the operating system.")
        defaults["rss"] = False

        self.add_option("--ignoreFirst",
                        action = "store_true", dest = "ignore_first",
                        help = "Alternative median calculation from pageloader data.  Use the raw values \
                                and discard the first page load instead of the highest value. [DEPRECATED: use `--filter ignore_first --filter median`]")
        defaults["ignore_first"] = False

        self.add_option("--filter",
                        action="append", dest='filters',
                        help="filters to apply to the data from talos.filters [DEFAULT: ignore_max, median]")
        defaults["filters"] = None # added in verifyCommandLine

        self.add_option("--amo",
                        action = "store_true", dest = "amo",
                        help = "set amo")
        defaults["amo"] = False

        self.add_option("--csvDir", dest="csv_dir",
                        action="store",
                        help="specify csv output file")
        defaults["csv_dir"] = ""

        self.add_option('--tpmanifest',
                        action='store', dest='tpmanifest',
                        help="manifest file to test")
        defaults["tpmanifest"] = ""
        self.add_option('--tpcycles', type='int',
                        action='store', dest='tpcycles',
                        help="number of pageloader cycles to run")
        defaults["tpcycles"] = None
        self.add_option('--tppagecycles', type='int',
                        action='store', dest='tppagecycles',
                        help="number of pageloader cycles to run for each page in the manifest")
        defaults["tppagecycles"] = None
        self.add_option('--tpdelay', type='int',
                        action='store', dest='tpdelay',
                        help="length of pageloader delay")
        defaults["tpdelay"] = None

        self.set_defaults(**defaults)

    def parse_args(self, args=None, values=None):
        self.parsed = set() # reset parsed args
        options, args = optparse.OptionParser.parse_args(self, args=args, values=values)
        options = self.verifyCommandLine(args, options)
        return options, args

    def verifyCommandLine(self, args, options):

        # if resultsServer and resultsLinks are given replace results_url from there
        if options.resultsServer and options.resultsLink:
            if options.results_url:
                raise Configuration("Can't use resultsServer/resultsLink and resultsURL; use resultsURL instead")
            options.results_url = 'http://%s%s' % (options.resultsServer, options.resultsLink)

        if options.develop == True:
            if options.webserver == '':
                options.webserver = "localhost:%s" % (findOpenPort('127.0.0.1'))

        # XXX delete deprecated values
        del options.resultsServer
        del options.resultsLink

        # XXX convert --ignoreFirst to the appropriate set of filters
        if options.ignore_first:
            if options.filters:
                raise Configuration("Can't use --ignoreFirst and --filter; use --filter instead")
            options.filters = ['ignore_first', 'median']

        # convert options.filters to [[filter, [args]]]
        if options.filters:
            for index, filter_name in enumerate(options.filters):
                try:
                    f = filter.parse(filter_name)
                except Exception, e:
                    raise Configuration("Bad value for filter '%s': %s" % (filter_name, e))
                options.filters[index] = f

        # fix up extraPrefs to be a list of 2-tuples
        options.extraPrefs = [i.split('=', 1) for i in options.extraPrefs]
        badPrefs = [i for i in options.extraPrefs if len(i) == 1] # ensure len=1
        if badPrefs:
            raise Configuration("Use PREF=VALUE for --setPref: %s" % badPrefs)

        return options

# Used for the --develop option where we dynamically create a webserver
def getLanIp():
    from mozdevice import devicemanager
    nettools = devicemanager.NetworkTools()
    ip = nettools.getLanIp()
    port = findOpenPort(ip)
    return "%s:%s" % (ip, port)

def findOpenPort(ip):
    from mozdevice import devicemanager
    nettools = devicemanager.NetworkTools()
    port = nettools.findOpenPort(ip, 15707)
    return str(port)

def main(argv=sys.argv[1:]):
    parser = TalosOptions()
    progname = parser.get_prog_name()

    try:
        options, args = parser.parse_args(argv)
        if args:
            raise Configuration("Configurator does not take command line arguments, only options (arguments were: %s)" % (",".join(args)))
        # ensure tests are supplied
        if not options.activeTests:
            raise Configuration("Active tests should be declared explicitly. Nothing declared with --activeTests.")
        configurator = PerfConfigurator(**options.__dict__);
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
