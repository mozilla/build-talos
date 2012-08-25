#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess
import sys
import xtalos

def stop(xperf_path, debug=False):
    xperf_cmd = [xperf_path, '-stop', '-stop', 'talos_ses']
    if debug:
        print "executing '%s'" % subprocess.list2cmdline(xperf_cmd)
    subprocess.call(xperf_cmd)

def main(args=sys.argv[1:]):

    # parse command line options
    parser = xtalos.XtalosOptions()
    options, args = parser.parse_args(args)
    options = parser.verifyOptions(options)
    if options is None:
        parser.error("Unable to verify options")

    # execute the command
    stop(options.xperf_path, options.debug_level >= xtalos.DEBUG_INFO)

if __name__ == "__main__":
    main()


