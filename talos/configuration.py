#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# taken from
# http://k0s.org/mozilla/hg/configuration/raw-file/9d19ed8fd883/configuration/configuration.py
# Please notify jhammel@mozilla.com if you change this file so that development
# can be upstreamed

"""
unified configuration with serialization/deserialization
"""

import copy
import os
import sys
import optparse

# imports for configuration providers
try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        json = None
try:
    import yaml
except ImportError:
    yaml = None

__all__ = ['Configuration',
           'configuration_providers',
           'types',
           'UnknownOptionException',
           'MissingValueException',
           'ConfigurationProviderException',
           'TypeCastException',
           'ConfigurationOption']

### exceptions

class UnknownOptionException(Exception):
    """exception raised when a non-configuration value is present in the configuration"""

class MissingValueException(Exception):
    """exception raised when a required value is missing"""

class ConfigurationProviderException(Exception):
    """exception raised when a configuration provider is missing, etc"""

class TypeCastException(Exception):
    """exception raised when a configuration item cannot be coerced to a type"""


### configuration providers for serialization/deserialization

configuration_providers = []

class ConfigurationProvider(object):
    """
    abstract base class for configuration providers for
    serialization/deserialization
    """
    def read(self, filename):
        raise NotImplementedError("Abstract base class")

    def write(self, config, filename):
        if isinstance(filename, basestring):
            f = file(filename, 'w')
            newfile = True
        else:
            f = filename
            newfile = False
        exception = None
        try:
            self._write(f, config)
        except Exception, exception:
            pass
        if newfile:
            f.close()
        if exception:
            raise exception
    def _write(self, fp, config):
        raise NotImplementedError("Abstract base class")

if json:
    class JSON(ConfigurationProvider):
        indent = 2
        extensions = ['json']
        def read(self, filename):
            return json.loads(file(filename).read())
        def _write(self, fp, config):
            fp.write(json.dumps(config, indent=self.indent, sort_keys=True))
            # TODO: could use templates to get order down, etc
    configuration_providers.append(JSON())

if yaml:
    class YAML(ConfigurationProvider):
        extensions = ['yml', 'yaml']
        dump_args = {'default_flow_style': False}
        def read(self, filename):
            f = file(filename)
            config = yaml.load(f)
            f.close()
            return config
        def _write(self, fp, config):
            fp.write(yaml.dump(config, **self.dump_args))
            # TODO: could use templates to get order down, etc

    configuration_providers.append(YAML())

# TODO: add configuration providers
# - for taking command-line arguments from a file
# - for .ini files

__all__.extend([i.__class__.__name__ for i in configuration_providers])

### optparse interface

class ConfigurationOption(optparse.Option):
    """option that keeps track if it is seen"""
    # TODO: this should be configurable or something
    def take_action(self, action, dest, opt, value, values, parser):

        # switch on types
        formatter = getattr(parser, 'cli_formatter')
        if formatter:
            formatter = formatter(dest)
            if formatter:
                value = formatter(value)

        # call the optparse front-end
        optparse.Option.take_action(self, action, dest, opt, value, values, parser)

        # add the parsed option to the set of things parsed
        if not hasattr(parser, 'parsed'):
            parser.parsed = dict()
        parser.parsed[dest] = value

### plugins for option types

class BaseCLI(object):
    """base_cli for all option types"""

    def __call__(self, name, value):
        """return args, kwargs needed to instantiate an optparse option"""

        args = value.get('flags', ['--%s' % name])
        if not args:
            # No CLI interface
            return (), {}

        kw = {'dest': name}
        help = value.get('help', name)
        if 'default' in value:
            kw['default'] = value['default']
            help += ' [DEFAULT: %s]' % value['default']
        kw['help'] = help
        kw['action'] = 'store'
        return args, kw

    def take_action(self, value):
        return value

class BoolCLI(BaseCLI):

    def __call__(self, name, value):

        # preserve the default values
        help = value.get('help')
        flags = value.get('flags')

        args, kw = BaseCLI.__call__(self, name, value)
        kw['help'] = help # reset
        if value.get('default'):
            kw['action'] = 'store_false'
            if not flags:
                args = ['--no-%s' % name]
            if not help:
                kw['help'] = 'disable %s' % name
        else:
            kw['action'] = 'store_true'
            if not help:
                kw['help'] = 'enable %s' % name
        return args, kw

class ListCLI(BaseCLI):

    def __call__(self, name, value):
        args, kw = BaseCLI.__call__(self, name, value)

        # TODO: could use 'extend'
        # - http://hg.mozilla.org/build/mozharness/file/5f44ba08f4be/mozharness/base/config.py#l41

        kw['action'] = 'append'
        return args, kw

class IntCLI(BaseCLI):

    def __call__(self, name, value):
        args, kw = BaseCLI.__call__(self, name, value)
        kw['type'] = 'int'
        return args, kw

class FloatCLI(BaseCLI):

    def __call__(self, name, value):
        args, kw = BaseCLI.__call__(self, name, value)
        kw['type'] = 'float'
        return args, kw

class DictCLI(ListCLI):

    delimeter = '='

    def __call__(self, name, value):

        # optparse can't handle dict types OOTB
        default = value.get('default')
        if isinstance(default, dict):
            value = copy.deepcopy(value)
            value['default'] = default.items()

        return ListCLI.__call__(self, name, value)

    def take_action(self, value):
        if self.delimeter not in value:
            raise AssertionError("Each value must be delimited by '%s': %s" % (self.delimeter, value))
        return value.split(self.delimeter, 1)

types = {bool:  BoolCLI(),
         int:   IntCLI(),
         float: FloatCLI(),
         list:  ListCLI(),
         dict:  DictCLI(),
         str:   BaseCLI(),
         None:  BaseCLI()} # default

__all__ += [i.__class__.__name__ for i in types.values()]

class Configuration(optparse.OptionParser):
    """declarative configuration object"""

    options = {}         # configuration basis definition
    load_option = 'load' # where to put the load option
    extend = set()       # if dicts/lists should be extended

    def __init__(self, configuration_providers=configuration_providers, types=types, load=None, dump='--dump', **parser_args):

        # sanity check
        if isinstance(self.options, dict):
            self.option_dict = self.options
        elif isinstance(self.options, list):
            # XXX could also be tuple, etc
            self.option_dict = dict(self.options)
        else:
            raise NotImplementedError

        # setup configuration
        self.config = {}
        self.configuration_providers = configuration_providers
        self.types = types
        self.added = set() # set of items added to the configuration

        # setup optionparser
        if 'description' not in parser_args:
            parser_args['description'] = getattr(self, '__doc__', '')
            if 'formatter' not in parser_args:
                class PlainDescriptionFormatter(optparse.IndentedHelpFormatter):
                    """description formatter for console script entry point"""
                    def format_description(self, description):
                        if description:
                            return description.strip() + '\n'
                        else:
                            return ''
                parser_args['formatter'] = PlainDescriptionFormatter()
        parser_args.setdefault('option_class', ConfigurationOption)
        optparse.OptionParser.__init__(self, **parser_args)
        self.parsed = dict()
        self.optparse_options(self)
        # add option(s) for configuration_providers
        if load:
            self.add_option(load,
                            dest=self.load_option, action='append',
                            help="load configuration from a file")

        # add an option for dumping
        formats = self.formats()
        if formats and dump:
            if isinstance(dump, basestring):
                dump = [dump]
            dump = list(dump)
            self.add_option(*dump, **dict(dest='dump',
                                          help="Output configuration file; Formats: %s" % formats))


    ### methods for iteration
    ### TODO: make the class a real iterator

    def items(self):
        # allow options to be a list of 2-tuples
        if isinstance(self.options, dict):
            return self.options.items()
        return self.options

    ### methods for validating configuration

    def check(self, config):
        """
        check validity of configuration to be added
        """

        # ensure options in configuration are in self.options
        unknown_options = [i for i in config if i not in self.option_dict]
        if unknown_options:
            raise UnknownOptionException("Unknown options: %s" % ', '.join(unknown_options))

        # ensure options are of the right type (if specified)
        for key, value in config.items():
            _type = self.option_dict[key].get('type')
            if _type is None and 'default' in self.option_dict[key]:
                _type = type(self.option_dict[key]['default'])
            if _type is not None:
                tocast = True
                try:
                    if isinstance(value, _type):
                        tocast = False
                except TypeError:
                    # type is a type-casting function, not a proper type
                    pass
                if tocast:
                    try:
                        config[key] = _type(value)
                    except BaseException, e:
                        raise TypeCastException("Could not coerce %s, %s, to type %s: %s" % (key, value, _type.__name__, e))

        return config

    def validate(self):
        """validate resultant configuration"""

        for key, value in self.items():
            if key not in self.config:
                required = value.get('required')
                if required:
                    if isinstance(required, basestring):
                        required_message = required
                    else:
                        required_message = "Parameter %s is required but not present" % key
                    # TODO: this should probably raise all missing values vs
                    # one by one
                    raise MissingValueException(required_message)
        # TODO: configuration should be locked after this is called

    ### methods for adding configuration

    def default_config(self):
        """configuration defaults"""
        defaults = {}
        for key, value in self.items():
            if 'default' in value:
                defaults[key] = value['default']
        return copy.deepcopy(defaults)

    def __call__(self, *args):
        """add items to configuration and check it"""
        # TODO: configuration should be locked after this is called

        # start with defaults
        self.config = self.default_config()

        # add the configuration
        for config in args:
            self.add(config)

        # validate total configuration
        self.validate()

        # return the configuration
        return self.config

    def add(self, config, check=True):
        """update configuration: not undoable"""

        # check config to be added
        self.check(config)

        # add the configuration
        for key, value in config.items():
            value = copy.deepcopy(value)
            if key in self.extend and key in self.config:
                type1 = type(self.config[key])
                type2 = type(value)
                assert type1 == type2 # XXX hack
                if type1 == dict:
                    self.config[key].update(value)
                elif type1 == list:
                    self.config[key].extend(value)
                else:
                    raise NotImplementedError
            else:
                self.config[key] = value
            self.added.add(key)


    ### methods for optparse
    ### XXX could go in a subclass

    def cli_formatter(self, option):
        if option in self.option_dict:
            handler = self.types[self.option_type(option)]
            return getattr(handler, 'take_action', lambda x: x)

    def option_type(self, name):
        """get the type of an option named `name`"""

        value = self.option_dict[name]
        if 'type' in value:
            return value['type']
        if 'default' in value:
            default = value['default']
            if default is None:
                return None
            return type(value['default'])

    def optparse_options(self, parser):
        """add optparse options to a OptionParser instance"""
        for key, value in self.items():
            try:
                handler = self.types[self.option_type(key)]
            except KeyError:
                # if an option can't be coerced to a type
                # we should just not add a CLI handler for it
                continue
            args, kw = handler(key, value)
            if not args:
                # No CLI interface
                continue
            parser.add_option(*args, **kw)

    def parse_args(self, *args, **kw):

        self.parsed = dict()
        options, args = optparse.OptionParser.parse_args(self, *args, **kw)

        # get CLI configuration options
        cli_config = dict([(key, value) for key, value in options.__dict__.items()
                           if key in self.option_dict and key in self.parsed])

        # deserialize configuration
        configuration_files = getattr(options, self.load_option, args)
        if not configuration_files:
            configuration_files = []
        if isinstance(configuration_files, basestring):
            configuration_files = [configuration_files]
        missing = [i for i in configuration_files
                   if not os.path.exists(i)]
        if missing:
            self.error("Missing files: %s" % ', '.join(missing))
        config = []
        for f in configuration_files:
            try:
                loaded_config = self.deserialize(f)
                if loaded_config:
                    config.append(loaded_config)
            except BaseException, e:
                parser.error(str(e))
        config.append(cli_config)

        missingvalues = None
        try:
            # generate configuration
            self(*config)
        except MissingValueException, missingvalues:
            # errors are handled below
            pass

        # dump configuration
        self.dump(options, missingvalues)

        # update options from config
        options.__dict__.update(self.config)

        # return parsed arguments
        return options, args

    def dump(self, options, missingvalues):
        """dump configuration, if specified"""

        if missingvalues:
            self.error(str(missingvalues))

        dump = getattr(options, 'dump')
        if dump:
            # TODO: have a way of specifying format other than filename
            self.serialize(dump)

    ### serialization/deserialization

    def formats(self):
        """formats for deserialization"""
        retval = []
        for provider in self.configuration_providers:
            if provider.extensions and hasattr(provider, 'write'):
                retval.append(provider.extensions[0])
        return retval

    def configuration_provider(self, format):
        """configuration provider guess for a given filename"""
        for provider in self.configuration_providers:
            if format in provider.extensions:
                return provider

    def filename2format(self, filename):
        extension = os.path.splitext(filename)[-1]
        return extension.lstrip('.') or None

    def serialize(self, filename, format=None, full=False):
        """
        serialize configuration to a file
        - filename: path of file to serialize to
        - format: format of configuration provider
        - full: whether to serialize non-set optional strings [TODO]
        """
        # TODO: allow file object vs file name

        if not format:
            format = self.filename2format(filename)
            if not format:
                raise Exception('Please specify a format')
                # TODO: more specific exception type

        provider = self.configuration_provider(format)
        if not provider:
            raise Exception("Provider not found for format: %s" % format)

        config = copy.deepcopy(self.config)

        provider.write(config, filename)

    def deserialize(self, filename, format=None):
        """load configuration from a file"""
        # TODO: allow file object vs file name

        assert os.path.exists(filename)

        # get the format
        if not format:
            format = self.filename2format(filename)

        # get the providers in some sensible order
        providers = self.configuration_providers[:]
        if format:
            providers.sort(key=lambda x: int(format in x.extensions), reverse=True)

        # deserialize the data
        for provider in providers:
            try:
                return provider.read(filename)
            except:
                continue
        else:
            raise ConfigurationProviderException("Could not load %s" % filename)
