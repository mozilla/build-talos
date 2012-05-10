#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
performance configuration for remote Talos
"""

import copy
import os
import sys
import utils
import PerfConfigurator as pc

class remotePerfConfigurator(pc.PerfConfigurator):

    # use options from PerfConfigurator
    options = copy.deepcopy(pc.PerfConfigurator.options) + [
        ('nativeUI', {'help': 'Run tests on Fennec with a Native Java UI instead of the XUL UI',
                      'default': False})
        ]

    preferences = copy.deepcopy(pc.PerfConfigurator.preferences)

    # remote-specific options
    remote_options = {
        'deviceip': {'help': 'Device IP (when using SUTAgent)',
                     'flags': ['-r', '--remoteDevice']},
        'deviceport': {'help': "SUTAgent port (defaults to 20701, specify -1 to use ADB)",
                       'default': 20701,
                       'flags': ['-p', '--remotePort']},
        'deviceroot': {'help': 'path on the device that will hold files and the profile',
                       'flags': ['--deviceRoot']},
        'fennecIDs': {'help': 'Location of the fennec_ids.txt map file, used for robocop based tests',
                      'flags': ['--fennecIDs']},
        'remote': {'default': False,
                   'flags': []},
        }

    # remote-specific defaults
    default_values = {'basetest': {'timeout': 3600,
                                   'profile_path': '${talos}/mobile_profile',
                                   'remote_counters': [],
                                   'tpcycles': 3,
                                   'tpdelay': 1000
                                   },
                      'browser_wait': 20,
                      'test_timeout': 3600,
                      'env': {'MOZ_CRASHREPORTER_NO_REPORT': '1',
                              'MOZ_CRASHREPORTER_SHUTDOWN': '1'},
                      'dirs': {'chrome': '${talos}/page_load_test/chrome',
                               'components': '${talos}/page_load_test/components'},
                      'process': 'fennec',
                      'title': 'mobile',
                      'test_overrides': {'ts':
                                             {'cycles': 20,
                                              'timeout': 150},
                                         'ts_paint':
                                             {'cycles': 20},
                                         'ts_places_generated_max':
                                             {'cycles': 10,
                                              'timeout': 150},
                                         'ts_places_generated_min':
                                             {'cycles': 10,
                                              'timeout': 150},
                                         'ts_places_generated_med':
                                             {'cycles': 10,
                                              'timeout': 150},
                                         'tdhtml':
                                             {'tpcycles': 3},
                                         'tsvg':
                                             {'tpcycles': 3},
                                         'tsspider':
                                             {'tpcycles': 3}
                                         }
                      }

    ### overrides of PerfConfigurator methods

    def __init__(self, **kwargs):

        self.remote = False

        # remote-specific preferences
        self.preferences.update({'talos.logfile': 'browser_output.txt',
                                 'network.manage-offline-status': False})
        for pref in ['network.proxy.http',
                     'network.proxy.http_port',
                     'network.proxy.type',
                     'browser.bookmarks.max_backups',
                     'dom.max_chrome_script_run_time']:
            # remove preferences not applicable to remote
            self.preferences.pop(pref)

        # add remote-specific options
        names = [i[0] for i in self.options]
        for key, value in self.remote_options.items():
            index = names.index(key)
            self.options[index][-1].update(value)

        # initialize PerfConfigurator
        pc.PerfConfigurator.__init__(self, **kwargs)

        # add remote-specific defaults
        for key, value in self.default_values.items():
            default = self.option_dict[key].get('default')
            if isinstance(default, dict):
                default.update(value)
            else:
                self.option_dict[key]['default'] = value

    def validate(self):

        # setup remote
        deviceip = self.config.get('deviceip')
        deviceport = self.config['deviceport']
        if deviceip or deviceport == -1:
            self._setupRemote(deviceip, deviceport)

        # For NativeUI Fennec, we are working around bug 708793 and uploading a
        # unique machine name (defined via title) with a .n.  Currently a machine name
        # is a 1:1 mapping with the OS+hardware
        if self.config.pop('nativeUI') and not self.config['title'].endswith(".n"):
            self.config['title'] = "%s.n" % self.config['title']

        # fix webserver for --develop mode
        if self.config.get('develop'):
            webserver = self.config.get('webserver')
            if (not webserver) or (webserver == 'localhost'):
                self.config['webserver'] = utils.getLanIp()

        # webServer can be used without remoteDevice, but is required when using remoteDevice
        if self.config.get('deviceip') or self.config.get('deviceroot'):
            if self.config.get('webserver', 'localhost') == 'localhost' or not self.config.get('deviceip'):
                raise pc.ConfigurationError("When running Talos on a remote device, you need to provide a webServer and optionally a remotePort")

        fennecIDs = self.config.get('fennecIDs')
        if fennecIDs and not os.path.exists(fennecIDs):
            raise pc.ConfigurationError("Unable to find fennce IDs file, please ensure this file exists: %s" % fennecIDs)

        # use parent class validator
        pc.PerfConfigurator.validate(self)

        self.config['remote'] = self.remote

        # fix up logfile preference
        logfile = self.config['preferences'].get('talos.logfile')
        if logfile:
            # use the last part of the browser_log overridden for the remote log
            # from the global; see
            # http://hg.mozilla.org/build/talos/file/c702ff8892be/talos/remotePerfConfigurator.py#l45
            self.config['preferences']['talos.logfile'] = '%s/%s' % (self.deviceroot, logfile.split('/')[-1])

    def convertUrlToRemote(self, url):
        """
        For a give url, add a webserver.
        In addition if there is a .manifest file specified, covert
        and copy that file to the remote device.
        """
        url = pc.PerfConfigurator.convertUrlToRemote(self, url)
        if self.remote == False:
            return url
        if 'winopen.xul' in url:
            self.buildRemoteTwinopen()
            url = 'file://' + self.deviceroot + '/talos/' + url

        # Take care of tpan/tzoom tests
        url = url.replace('webServer=', 'webServer=%s' % self.config['webserver'])

        # Take care of the robocop based tests
        url = url.replace('class org.mozilla.fennec.tests', 'class %s.tests' % self.config['browser_path'])
        return url

    def buildRemoteManifest(self, manifestName):
        """
        Push the manifest name to the remote device.
        """
        remoteName = self.deviceroot
        newManifestName = pc.PerfConfigurator.buildRemoteManifest(self, manifestName)

        remoteName += '/' + os.path.basename(manifestName)
        if self.testAgent.pushFile(newManifestName, remoteName) == False:
            msg = "Unable to copy remote manifest file %s to %s" % (newManifestName, remoteName)
            raise pc.ConfigurationError(msg)
        return remoteName

    ### remotePerfConfigurator specific methods

    def _setupRemote(self, deviceip, deviceport):

        try:
            self.testAgent = utils.testAgent(deviceip, deviceport)
            self.deviceroot = self.testAgent.getDeviceRoot()
        except:
            raise pc.ConfigurationError("Unable to connect to remote device '%s'" % deviceip)

        if self.deviceroot is None:
            raise pc.ConfigurationError("Unable to connect to remote device '%s'" % deviceip)

        self.config['deviceroot'] = self.deviceroot
        self.remote = True

    def buildRemoteTwinopen(self):
        """
        twinopen needs to run locally as it is a .xul file.
        copy bits to <deviceroot>/talos and fix line to reference that
        """
        # XXX this should live in run_test.py or similar

        if self.remote == False:
            return

        files = ['page_load_test/quit.js',
                 'scripts/MozillaFileLogger.js',
                 'startup_test/twinopen/winopen.xul',
                 'startup_test/twinopen/winopen.js',
                 'startup_test/twinopen/child-window.html']

        talosRoot = self.deviceroot + '/talos/'
        for file in files:
            if self.testAgent.pushFile(file, talosRoot + file) == False:
                raise pc.ConfigurationError("Unable to copy twinopen file "
                                            + file + " to " + talosRoot + file)

def main(args=sys.argv[1:]):

    # generate a configuration from command-line arguments
    conf = remotePerfConfigurator(usage='%prog [options]')

    # XXX add PerfConfigurator-specific override for load since
    # Perfconfigurator and talos console_script entry points differ
    conf.add_option("-f", "--sampleConfig", dest="load",
                    action="append",
                    help="Input config file")

    # parse the arguments and dump an output file
    conf.parse_args(args)
    return 0

if __name__ == '__main__':
    sys.exit(main())
