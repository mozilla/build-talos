# vim:se?t ts=2 sw=2 sts=2 et cindent:
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. */

import os
import sys
import platform
import optparse
# Talos specific imports
import talos.utils
import talos.talosProcess
import mozhttpd
# media test utilities
import media_utils

"""
MediaManager serves as entry point for running media performance tests.
It is responsible for the following
1. Manage life-cycle of the mozHttpdServer and browser instance
2. Provide RESTP API handlers for the Media tests
3. REST API design follows the pattern
     <resource>/<component>/<operation>
     Example: audio recorder functionality
          ==> audio/recorder/start, audio/recorder/stop
          For audio pesq functionality
          ==> audio/pesq/compute
          For Stopping the server and browser
          ==> server/config/stop

    The idea here is to allow easy specification of resources
    (audio, video, server) , components (tools such as PESQ, SOX)
    and the operations on them (start, stop, computue..)
"""

# This path is based on the ${talos}
# This page gets loaded as default home page for running the media tests.
__TEST_HTML_PAGE__ = "http://localhost:16932/startup_test/media/html/media_tests.html"

# Browser process timeout
__BROWSER_TIME_OUT__ = 7200

"""
ObjectDb serves as a global storage to hold object handles needed
during manager's operation. It holds browser process handle, httpd
server handle and reference to the Audio Utils object.
"""
class ObjectDb(object):
    browser_proc = None
    httpd_server = None
    audio_utils  = None

"""
URI Handlers and Parsers
"""
def errorMessage(message):
    return (500, {'ERROR': message})

@mozhttpd.handlers.json_response
def parseGETUrl(request):
    # Parse the url and invoke appropriate handlers
    url_path = request.path.lower()
    if url_path.find('audio') != -1:
        return (handleAudioRequest(request))
    elif url_path.find('server') != -1:
        return (handleServerConfigRequest(request))
    else:
        return errorMessage(request.path)

# Handler for Server Configuration Commands
def handleServerConfigRequest(request):
    # Stopping server is the only operation supported
    if request.path == '/server/config/stop':
        ObjectDb.browser_proc.kill()
        ObjectDb.httpd_server.stop()
    else:
        return errorMessage(request.path)

# Handler Audio Resource Command
def handleAudioRequest(request):
    # is this a recorder API
    if request.path.find('recorder') != -1:
        return (parseAudioRecorderRequest(request))
    elif request.path.find('pesq') != -1:
        return(parsePESQRequest(request))
    else:
        return errorMessage(request.path)

# Handle all the audio recorder operations
def parseAudioRecorderRequest(request):
    request_params = {}
    # check if there are params
    params = request.query.split(',')
    if request.path.find('start') != -1:
        for items in params:
            (name, value) = items.split('=')
            if name.startswith('timeout') == True:
                status,message = ObjectDb.audio_utils.startRecording(value)
                if status == True:
                    return (200, {'Start-Recording' : message})
                else:
                    return errorMessage(message)
    elif request.path.find('stop') != -1:
        ObjectDb.audio_utils.stopRecording()
        return (200, {'Stop-Recording' : 'Success'})
    else:
        return errorMessage(request.path)

# Parse PESQ Get Request
def parsePESQRequest(request):
    if request.path.find('compute') != -1:
        status,message = ObjectDb.audio_utils.computePESQScore();
        if status == True:
            return (200, {'PESQ-SCORE' : message})
        else:
            return errorMessage(message)
    else:
        return errorMessage(request.path)

# Run HTTPD server and setup URL path handlers
# doc_root is set to ${talos} when invoked from the talos
def run_server(doc_root):
    httpd_server = mozhttpd.MozHttpd(port=16932, docroot=doc_root,
                                     urlhandlers = [ { 'method'   : 'GET',
                                                       'path'     : '/audio/',
                                                       'function' : parseGETUrl },
                                                     { 'method'   : 'GET',
                                                       'path'     : '/server/?',
                                                       'function' : parseGETUrl } ])
    talos.utils.info("Server %s at %s:%s" ,
      httpd_server.docroot, httpd_server.host, httpd_server.port)
    ObjectDb.httpd_server = httpd_server
    httpd_server.start(block=True)

"""
Kick-off the firefox process with passed in profile
talos_results_url is appended to the URL loaded if passed in
during invocation. This enables the test page to dump the
results to Talos MozHttpdServer
"""
def open_browser(browser, profile):
    url = __TEST_HTML_PAGE__
    if ObjectDb.talos_results_url:
        url =  url + "?" + "results="+ObjectDb.talos_results_url

    command = [ browser, '-profile', profile, '-no-remote', url]
    command = [str(s) for s in command]
    try:
        browser_proc = talos.talosProcess.talosProcess(command,
                                                   env=os.environ.copy())
        browser_proc.run(timeout=__BROWSER_TIME_OUT__)
    except Exception, e:
        if ObjectDb.httpd_server:
            ObjectDb.httpd_server.stop()

    ObjectDb.browser_proc = browser_proc

if __name__ == "__main__":
    # Linux platform is supported
    if not platform.system() == "Linux":
        print "This version of the tool supports only Linux"
        sys.exit(0)

    parser = optparse.OptionParser()
    """
    No validation of options are done since we control
    this program from within the Talos.
    TODO: provide validation once stand-alone usage
    is supported
    """
    parser.add_option("-p","--profile", dest="profile",
                      help="Firefox User Profile",)
    parser.add_option("-b","--browser", dest="browser",
                      help="Firefox Browser Exeuctable Path",)
    parser.add_option("-t","--talos", dest="talos_path",
                      help="Talos Path to serves as docroot",)
    parser.add_option("-r","--results_url", dest="talos_results",
                      help="Talos Results Url",)
    (options, args) = parser.parse_args()

    ObjectDb.talos_results_url = options.talos_results

    # 1. Create handle to the AudioUtils
    ObjectDb.audio_utils = media_utils.AudioUtils()

    # 2. Kick off the browser
    open_browser(options.browser, options.profile)

    # 3. Start the httpd server
    run_server(options.talos_path)
