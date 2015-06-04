import os


def writeConfigFile(obj, vals):
    return ''.join("%s: %s\n" % (opt, obj[opt])
                   for opt in (vals or obj.keys()))


def generateTalosConfig(command_line, browser_config, test_config, pid=None):
    bcontroller_vars = ['command', 'child_process', 'process', 'browser_wait',
                        'test_timeout', 'browser_log', 'browser_path',
                        'error_filename']

    if 'xperf_path' in browser_config:
        bcontroller_vars.append('xperf_path')
        bcontroller_vars.extend(['buildid', 'sourcestamp', 'repository',
                                 'title'])
        if 'name' in test_config:
            bcontroller_vars.append('testname')
            browser_config['testname'] = test_config['name']

    if (browser_config['webserver'] != 'localhost'):
        bcontroller_vars.extend(['host', 'port', 'deviceroot', 'env'])

    browser_config['command'] = ' '.join(command_line)

    if (('xperf_providers' in test_config) and
        ('xperf_user_providers' in test_config) and
        ('xperf_stackwalk' in test_config)):  # noqa

        print "extending with xperf!"
        browser_config['xperf_providers'] = test_config['xperf_providers']
        browser_config['xperf_user_providers'] = \
            test_config['xperf_user_providers']
        browser_config['xperf_stackwalk'] = test_config['xperf_stackwalk']
        browser_config['processID'] = pid
        browser_config['approot'] = \
            os.path.dirname(browser_config['browser_path'])
        bcontroller_vars.extend(['xperf_providers', 'xperf_user_providers',
                                 'xperf_stackwalk', 'processID', 'approot'])

    content = writeConfigFile(browser_config, bcontroller_vars)

    with open(browser_config['bcontroller_config'], "w") as fhandle:
        fhandle.write(content)

    return content
