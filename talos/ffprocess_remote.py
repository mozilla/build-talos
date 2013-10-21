# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is standalone Firefox Windows Mobile performance test.
#
# Contributor(s):
#   Joel Maher <joel.maher@gmail.com> (original author)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
from ffprocess import FFProcess
import os
import time
import tempfile
import shutil
from utils import talosError, testAgent
try:
    import mozdevice
except:
    # mozdevice is known not to import correctly with python 2.4, which we
    # still support
    pass

DEFAULT_PORT = 20701

class RemoteProcess(FFProcess):
    testAgent = None
    rootdir = ''
    dirSlash = ''
    host = ''
    port = ''

    def __init__(self, host, port, rootdir):
        if not port:
            port = DEFAULT_PORT

        self.port = port
        self.host = host
        self.setupRemote(host, port)
        self.rootdir = rootdir
        parts = self.rootdir.split("\\")
        if (len(parts) > 1):
            self.dirSlash = "\\"
        else:
            self.dirSlash = "/"

    def setupRemote(self, host='', port=DEFAULT_PORT):
        self.testAgent = testAgent(host, port)

    def GetRunningProcesses(self):
        try:
            return self.testAgent.getProcessList()
        except mozdevice.DMError:
            print "Remote Device Error: Error getting list of processes on remote device"
            raise  

    def ProcessesWithNames(self, *process_names):
        """Returns a list of processes running with the given name(s).
        Useful to check whether a Browser process is still running

        Args:
            process_names: String or strings containing process names, i.e. "firefox"

        Returns:
            An array with a list of processes in the list which are running
        """

        # refresh list of processes
        data = self.GetRunningProcesses()
        if not data:
            return []

        processes_with_names = []
        for process_name in process_names:
            try:
                for pid, appname, userid in data:
                    if process_name == appname:
                        processes_with_names.append((pid, process_name))
            except:
                # Might get an exception if there are no instances of the process running.
                continue
        return processes_with_names

    def TerminateAllProcesses(self, timeout, *process_names):
        """Helper function to terminate all processes with the given process name

        Args:
          process_name: String or strings containing the process name, i.e. "firefox"
        """
        result = ''
        for process_name in process_names:
            try:
                self.testAgent.killProcess(process_name)
                if result:
                    result = result + ', '
                result += process_name + ': terminated by testAgent.killProcess'
            except mozdevice.DMError:
                print "Remote Device Error: Error while killing process '%s'" % process_name
                raise
        return result


    def getFile(self, remote_filename, local_filename = None):
        data = ''
        try:
            if self.testAgent.fileExists(remote_filename):
                data = self.testAgent.pullFile(remote_filename)
        except mozdevice.DMError:
            print "Remote Device Error: Error pulling file %s from " \
                "device" % remote_filename
            raise

        # if localfile is defined we need to cache its output for later
        # reading
        if local_filename:
            f = open(local_filename, 'w')
            f.write(data)
            f.close()

        return data

    def recordLogcat(self):
        self.testAgent.recordLogcat()

    def getLogcat(self):
        return self.testAgent.getLogcat()

    def launchProcess(self, cmd, outputFile = "process.txt", timeout = -1):
        if (outputFile == "process.txt"):
            outputFile = self.rootdir + self.dirSlash + "process.txt"
            cmd += " > " + outputFile
        try:
            cmds = cmd.split()
            waitTime = 30
            if cmds[0] == 'am' and cmds[1] == "instrument":
                waitTime = 0
            if (self.testAgent.fireProcess(cmd, maxWaitTime=waitTime) is None):
                return None
            handle = outputFile

            timed_out = True
            if (timeout > 0):
                total_time = 0
                while total_time < timeout:
                    time.sleep(5)
                    if not self.testAgent.processExist(cmd):
                        timed_out = False
                        break
                    total_time += 1

                if (timed_out == True):
                    return None

                return handle
        except mozdevice.DMError:
            print "Remote Device Error: Error launching process '%s'" % cmd
            raise

    #currently this is only used during setup of newprofile from ffsetup.py
    def copyDirToDevice(self, localDir):
        head, tail = os.path.split(localDir)

        remoteDir = self.rootdir + self.dirSlash + tail
        try:
            self.testAgent.pushDir(localDir, remoteDir)
        except mozdevice.DMError:
            print "Remote Device Error: Unable to copy '%s' to remote " \
                "device '%s'" % (localDir, remoteDir)
            raise

        return remoteDir
  
    def removeDirectory(self, dir):
        try:
            self.testAgent.removeDir(dir)
        except mozdevice.DMError:
            print "Remote Device Error: Unable to remove directory on remote device"
            raise

    def MakeDirectoryContentsWritable(self, dir):
        pass

    def removeFile(self, filename):
        try:
            self.testAgent.removeFile(filename)
        except mozdevice.DMError:
            print "Remote Device Error: Unable to remove file '%s' on " \
                "remote device" % dir
            raise

    def copyFile(self, fromfile, toDir):
        toDir = toDir.replace("/", self.dirSlash)
        toFile = toDir + self.dirSlash + os.path.basename(fromfile)
        try:
            self.testAgent.pushFile(fromfile, toFile)
        except mozdevice.DMError:
            print "Remote Device Error: Unable to copy file '%s' to directory '%s' on the remote device" % (fromfile, toDir)
            raise

    def getCurrentTime(self):
        #we will not raise an error here because the functions that depend on this do their own error handling
        data = self.testAgent.getCurrentTime()
        return data

    def getDeviceRoot(self):
        #we will not raise an error here because the functions that depend on this do their own error handling
        data = self.testAgent.getDeviceRoot()
        return data


    def runProgram(self, browser_config, command_args, timeout=1200):
        remoteLog = os.path.join(self.getDeviceRoot() + '/' + browser_config['browser_log'])
        self.removeFile(remoteLog)
        # bug 816719, remove sessionstore.js so we don't interfere with talos
        self.removeFile(os.path.join(self.getDeviceRoot(), "profile/sessionstore.js"))

        env = ""
        for key, value in browser_config['env'].items():
            env = "%s %s=%s" % (env, key, value)
        command_line = "%s %s" % (env, ' '.join(command_args))

        self.recordLogcat()
        firstTime = time.time()
        retVal = self.launchProcess(' '.join(command_args), outputFile=remoteLog, timeout=timeout)
        logcat = self.getLogcat()
        if logcat:
            with open('logcat.log', 'w') as f:
                f.write(''.join(logcat[-500:-1]))

        data = self.getFile(remoteLog, browser_config['browser_log'])
        with open(browser_config['browser_log'], 'a') as logfile:
            logfile.write("__startBeforeLaunchTimestamp%d__endBeforeLaunchTimestamp\n" % (firstTime * 1000))
            logfile.write("__startAfterTerminationTimestamp%d__endAfterTerminationTimestamp\n" % int(time.time() * 1000))
        if not retVal and data == '':
            raise talosError("missing data from remote log file")

        # Wait out the browser closing
        time.sleep(browser_config['browser_wait'])

