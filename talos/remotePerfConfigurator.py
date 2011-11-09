import PerfConfigurator as pc
from PerfConfigurator import Configuration
import os, sys
import optparse

class remotePerfConfigurator(pc.PerfConfigurator):
    def __init__(self, options):
        self.__dict__.update(options.__dict__)
        self._remote = False
        if (self.remoteDevice <> '' or self.remotePort == -1):
            self._setupRemote()
            options.deviceRoot = self.deviceRoot

        #this depends on buildID which requires querying the device
        pc.PerfConfigurator.__init__(self, options)
        pc.PerfConfigurator.attributes += ['remoteDevice', 'remotePort', 'deviceRoot']

    def _setupRemote(self):
        try:
            if (self.remotePort == -1):
                import devicemanagerADB
                self.testAgent = devicemanagerADB.DeviceManagerADB(self.remoteDevice, self.remotePort)
            else:
                import devicemanagerSUT
                self.testAgent = devicemanagerSUT.DeviceManagerSUT(self.remoteDevice, self.remotePort)

            self.deviceRoot = self.testAgent.getDeviceRoot()
        except:
            raise Configuration("Unable to connect to remote device '%s'" % self.remoteDevice)

        if (self.deviceRoot is None):
            raise Configuration("Unable to connect to remote device '%s'" % self.remoteDevice)

        self._remote = True

    def _dumpConfiguration(self):
        pc.PerfConfigurator._dumpConfiguration(self)

    def convertLine(self, line, testMode, printMe):
        printMe, newline = pc.PerfConfigurator.convertLine(self, line, testMode, printMe)
        if 'deviceip:' in line:
           newline = 'deviceip: %s\n' % self.remoteDevice
        if 'deviceroot:' in line:
            newline = 'deviceroot: %s\n' % self.deviceRoot
        if 'deviceport:' in line:
            newline = 'deviceport: %s\n' % self.remotePort
        if 'remote:' in line:
            newline = 'remote: %s\n' % self._remote
        if 'talos.logfile:' in line:
            parts = line.split(':')
            if (parts[1] != None and parts[1].strip() == ''):
                lfile = os.path.join(os.getcwd(), 'browser_output.txt')
            elif (self.logFile != 'browser_output.txt'):
                lfile = self.logFile
            else:
                lfile = parts[1].strip().strip("'")
            lfile = self.deviceRoot + '/' + lfile.split('/')[-1]
            newline = '%s: %s\n' % (parts[0], lfile)
        return printMe, newline

    def buildRemoteTwinopen(self):
        """
          twinopen needs to run locally as it is a .xul file.
          copy bits to <deviceroot>/talos and fix line to reference that
        """
        if self._remote == False:
            return

        files = ['page_load_test/quit.js',
                 'scripts/MozillaFileLogger.js',
                 'startup_test/twinopen/winopen.xul',
                 'startup_test/twinopen/winopen.js',
                 'startup_test/twinopen/child-window.html']

        talosRoot = self.deviceRoot + '/talos/'
        for file in files:
            if self.testAgent.pushFile(file, talosRoot + file) == False:
                raise Configuration("Unable to copy twinopen file "
                                    + file + " to " + talosRoot + file)

    def convertUrlToRemote(self, line):
        """
          For a give url line in the .config file, add a webserver.
          In addition if there is a .manifest file specified, covert 
          and copy that file to the remote device.
        """
        if self._remote == False:
            return line

        line = pc.PerfConfigurator.convertUrlToRemote(self, line)
        parts = line.split(' ')
        newline = ''
        for part in parts:
            if 'winopen.xul' in part:
                self.buildRemoteTwinopen()
                newline += 'file://' + self.deviceRoot + '/talos/' + part
            else:
                newline += part
                if (part <> parts[-1]):
                    newline += ' '

        #take care of tpan/tzoom tests
        newline = newline.replace('webServer=', 'webServer=' + self.webServer);
        return newline

    def buildRemoteManifest(self, manifestName):
        """
           Push the manifest name to the remote device.
        """
        remoteName = self.deviceRoot
        newManifestName = pc.PerfConfigurator.buildRemoteManifest(self, manifestName)

        remoteName += '/' + os.path.basename(manifestName)
        if self.testAgent.pushFile(newManifestName, remoteName) == False:
            raise Configuration("Unable to copy remote manifest file "
                                + newManifestName + " to " + remoteName)
        return remoteName

    def _getMasterIniContents(self):
        """ Open and read the application.ini on the device under test """
        if (self._remote == True):
            localfilename = "remoteapp.ini"
            
            #we need a better OS detection method, but for now this is how we work on android
            if (self.exePath.startswith('org.mozilla.f')):
              remoteFile = '/data/data/' + self.exePath + '/' + self.masterIniSubpath            
            else:
              parts = self.exePath.split('/')
              remoteFile = '/'.join(parts[0:-1]) + '/' + self.masterIniSubpath
            if (not os.path.isfile(localfilename)):
              filecontents = self.testAgent.getFile(remoteFile, localfilename)
              if not filecontents:
                  raise Configuration("Unable to copy master ini file from "
                                      "device - either it doesn't exist yet "
                                      "(have you run fennec at least once?) "
                                      "or you don't have permissions to get it "
                                      "(workaround: extract it from apk locally)")
              return fileContents.split('\n')

            master = open(localfilename)
        else:
            return pc.PerfConfigurator._getMasterIniContents(self)
            
        data = master.read()
        master.close()
        return data.split('\n')

class remoteTalosOptions(pc.TalosOptions):

    def __init__(self, **kwargs):
        defaults = {}
        pc.TalosOptions.__init__(self)

        self.add_option("-r", "--remoteDevice", action="store",
                    type = "string", dest = "remoteDevice",
                    help = "Device IP (when using SUTAgent)")
        defaults["remoteDevice"] = ''

        self.add_option("-p", "--remotePort", action="store",
                    type="int", dest = "remotePort",
                    help = "SUTAgent port (defaults to 20701, specify -1 to use ADB)")
        defaults["remotePort"] = 20701

        self.add_option("--deviceRoot", action="store",
                    type = "string", dest = "deviceRoot",
                    help = "path on the device that will hold files and the profile")
        defaults["deviceRoot"] = ''

        defaults["sampleConfig"] = 'remote.config'
        self.set_defaults(**defaults)

    def verifyCommandLine(self, args, options):
        options = pc.TalosOptions.verifyCommandLine(self, args, options)
    
        if options.develop:
            if options.webServer.startswith('localhost'):
                options.webServer = pc.getLanIp()

        #webServer can be used without remoteDevice, but is required when using remoteDevice
        if (options.remoteDevice != '' or options.deviceRoot != ''):
            if (options.webServer == 'localhost'  or options.remoteDevice == ''):
                raise Configuration("When running Talos on a remote device, you need to provide a webServer and optionally a remotePort")

def main(argv=None):
    parser = remoteTalosOptions()
    options, args = parser.parse_args()

    progname = sys.argv[0].split("/")[-1]
    try:
        parser.verifyCommandLine(args, options)
        configurator = remotePerfConfigurator(options)
        configurator.writeConfigFile()
    except Configuration, err:
        print >> sys.stderr, "%s: %s" % (progname, str(err.msg))
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
