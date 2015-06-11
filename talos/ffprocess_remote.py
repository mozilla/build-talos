# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from ffprocess import FFProcess
import os
import time
from utils import TalosError, testAgent
import mozdevice


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

    def getFile(self, remote_filename, local_filename=None):
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

    def launchProcess(self, cmd, processname, outputFile="process.txt",
                      timeout=-1):
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
                    if not self.testAgent.getTopActivity() == processname:
                        timed_out = False
                        break
                    total_time += 1

                if timed_out is True:
                    return None

                return handle
        except mozdevice.DMError:
            print "Remote Device Error: Error launching process '%s'" % cmd
            raise

    # currently this is only used during setup of newprofile from ffsetup.py
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
            print ("Remote Device Error: Unable to remove directory on"
                   " remote device")
            raise

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
            print ("Remote Device Error: Unable to copy file '%s' to directory"
                   " '%s' on the remote device" % (fromfile, toDir))
            raise

    def getCurrentTime(self):
        # we will not raise an error here because the functions that depend
        # on this do their own error handling
        data = self.testAgent.getCurrentTime()
        return data

    def getDeviceRoot(self):
        # we will not raise an error here because the functions that depend
        # on this do their own error handling
        data = self.testAgent.getDeviceRoot()
        return data

    def runProgram(self, browser_config, command_args, timeout=1200):
        remoteLog = os.path.join(
            self.getDeviceRoot() + '/' + browser_config['browser_log'])
        self.removeFile(remoteLog)
        # bug 816719, remove sessionstore.js so we don't interfere with talos
        self.removeFile(os.path.join(self.getDeviceRoot(),
                                     "profile/sessionstore.js"))

        env = ""
        for key, value in browser_config['env'].items():
            env = "%s %s=%s" % (env, key, value)

        self.recordLogcat()
        firstTime = time.time()
        retVal = self.launchProcess(' '.join(command_args),
                                    browser_config['browser_path'],
                                    outputFile=remoteLog,
                                    timeout=timeout)
        logcat = self.getLogcat()
        if logcat:
            with open('logcat.log', 'w') as f:
                f.write(''.join(logcat[-500:-1]))

        data = self.getFile(remoteLog, browser_config['browser_log'])
        with open(browser_config['browser_log'], 'a') as logfile:
            logfile.write(
                "__startBeforeLaunchTimestamp%d"
                "__endBeforeLaunchTimestamp\n"
                % (firstTime * 1000)
            )
            logfile.write(
                "__startAfterTerminationTimestamp%d"
                "__endAfterTerminationTimestamp\n"
                % int(time.time() * 1000)
            )
        if not retVal and data == '':
            raise TalosError("missing data from remote log file")

        # Wait out the browser closing
        time.sleep(browser_config['browser_wait'])
