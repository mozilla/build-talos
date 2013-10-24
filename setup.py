import os
import sys
from setuptools import setup, find_packages

try:
    here = os.path.dirname(os.path.abspath(__file__))
    description = file(os.path.join(here, 'README.txt')).read()
except IOError, OSError:
    description = ''

version = "0.0"

dependencies = ['PyYAML',
                'mozlog',
                'mozcrash == 0.9',
                'mozdevice == 0.26',
                'mozhttpd == 0.5',
                'mozinfo == 0.4',
                'datazilla == 1.4',
                'mozprocess == 0.11',
                'httplib2',
                'oauth2',
                ]
dependency_links = []

try:
    import json
except ImportError:
    # XXX you will need simplejson == 2.1.6 on python 2.4
    dependencies.append('simplejson')

setup(name='talos',
      version=version,
      description="A python performance testing framework that is usable on Windows, Mac and Linux.",
      long_description=description,
      classifiers=[], # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      author='Mozilla Foundation',
      author_email='tools@lists.mozilla.org',
      url='https://wiki.mozilla.org/Buildbot/Talos',
      license='MPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      package_data = {'': ['*.config',
                           '*.css',
                           '*.gif',
                           '*.htm',
                           '*.html',
                           '*.ico',
                           '*.js',
                           '*.json',
                           '*.manifest',
                           '*.php',
                           '*.png',
                           '*.rdf',
                           '*.sqlite',
                           '*.svg',
                           '*.xml',
                           '*.xul',
                           ]},
      zip_safe=False,
      install_requires=dependencies,
      dependency_links=dependency_links,
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      PerfConfigurator = talos.PerfConfigurator:main
      talos = talos.run_tests:main
      talos-results = talos.results:main
      """,
      test_suite = "runtests.runtests"
      )
