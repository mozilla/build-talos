# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import cStringIO
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import urllib2
import zipfile
from symFileManager import SymFileManager
from symbolicationRequest import SymbolicationRequest
from symLogging import LogMessage

class ProfileSymbolicator:
  def __init__(self, options):
    self.options = options
    self.sym_file_manager = SymFileManager(self.options)

  def integrate_symbol_zip_from_url(self, symbol_zip_url):
    if self.have_integrated(symbol_zip_url):
      return
    LogMessage("Retrieving symbol zip from {symbol_zip_url}...".format(symbol_zip_url=symbol_zip_url))
    io = urllib2.urlopen(symbol_zip_url, None, 30)
    sio = cStringIO.StringIO(io.read())
    zf = zipfile.ZipFile(sio)
    io.close()
    self.integrate_symbol_zip(zf)
    zf.close()
    self._create_file_if_not_exists(self._marker_file(symbol_zip_url))

  def integrate_symbol_zip_from_file(self, filename):
    if self.have_integrated(filename):
      return
    f = open(filename, 'r')
    zf = zipfile.ZipFile(f)
    self.integrate_symbol_zip(zf)
    f.close()
    zf.close()
    self._create_file_if_not_exists(self._marker_file(filename))

  def _create_file_if_not_exists(self, filename):
    try:
      os.makedirs(os.path.dirname(filename))
    except OSError:
      pass
    try:
      open(filename, 'a').close()
    except IOError:
      pass

  def integrate_symbol_zip(self, symbol_zip_file):
    symbol_zip_file.extractall(self.options["symbolPaths"]["FIREFOX"])

  def _marker_file(self, symbol_zip_url):
    marker_dir = os.path.join(self.options["symbolPaths"]["FIREFOX"], ".markers")
    return os.path.join(marker_dir, hashlib.sha1(symbol_zip_url).hexdigest())

  def have_integrated(self, symbol_zip_url):
    return os.path.isfile(self._marker_file(symbol_zip_url))

  def get_unknown_modules_in_profile(self, profile_json):
    if "libs" not in profile_json:
      return []
    shared_libraries = json.loads(profile_json["libs"])
    memoryMap = []
    for lib in shared_libraries:
      memoryMap.append(self._module_from_lib(lib))

    rawRequest = { "stacks": [[]], "memoryMap": memoryMap, "version": 4, "symbolSources": ["FIREFOX", "WINDOWS"] }
    request = SymbolicationRequest(self.sym_file_manager, rawRequest)
    if not request.isValidRequest:
      return []
    request.Symbolicate(0) # This sets request.knownModules

    unknown_modules = []
    for i, lib in enumerate(shared_libraries):
      if not request.knownModules[i]:
        unknown_modules.append(lib)
    return unknown_modules

  def dump_and_integrate_missing_symbols(self, profile_json, symbol_zip_path):
    # We only support dumping symbols on Mac at the moment.
    if platform.system() != "Darwin":
      return

    unknown_modules = self.get_unknown_modules_in_profile(profile_json)
    if not unknown_modules:
      return

    # Symbol dumping is done by a binary that lives in the same directory as this file.
    dump_syms_bin = os.path.join(os.path.dirname(__file__), 'dump_syms_mac')
    if not os.path.exists(dump_syms_bin):
      return

    # We integrate the dumped symbols by dumping them directly into our
    # symbol directory.
    output_dir = self.options["symbolPaths"]["FIREFOX"]

    # Additionally, we add all dumped symbol files to the missingsymbols zip file.
    zip = zipfile.ZipFile(symbol_zip_path, 'a', zipfile.ZIP_DEFLATED)

    rootlen = len(os.path.join(output_dir, '_')) - 1
    for lib in unknown_modules:
      [name, breakpadId] = self._module_from_lib(lib)
      expected_name = os.path.join(name, breakpadId, name) + '.sym'
      if expected_name in zip.namelist():
        # No need to dump the symbols again if we already have it in the
        # missingsymbols zip file from a previous run.
        zip.extract(expected_name, output_dir)
        continue

      lib_path = lib['name']
      if not os.path.exists(lib_path):
        continue

      # Dump the symbols.
      sym_file = self.store_symbols(lib_path, dump_syms_bin, output_dir)
      if sym_file:
        actual_name = sym_file[rootlen:]
        if expected_name != actual_name:
          LogMessage("Got unexpected name for symbol file, expected {0} but got {1}.".format(expected_name, actual_name))
        if actual_name not in zip.namelist():
          zip.write(sym_file, actual_name)
    zip.close()

  def store_symbols(self, fullpath, dump_syms_bin, output_directory):
    """
    Returns the filename at which the .sym file was created, or None if no
    symbols were dumped.
    """

    def should_process(f):
      if f.endswith(".dylib") or os.access(f, os.X_OK):
        return subprocess.Popen(["file", "-Lb", f], stdout=subprocess.PIPE).communicate()[0].startswith("Mach-O")
      return False

    def get_archs(filename):
      """
      Find the list of architectures present in a Mach-O file.
      """
      return subprocess.Popen(["lipo", "-info", filename], stdout=subprocess.PIPE).communicate()[0].split(':')[2].strip().split()

    def process_file(path, arch, verbose):
      proc = subprocess.Popen([dump_syms_bin, "-a", arch, path],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
      stdout, stderr = proc.communicate()
      if proc.returncode != 0:
        if verbose:
          print "Processing %s [%s]...failed.\n" % (path, arch)
        return
      module = stdout.splitlines()[0]
      bits = module.split(" ", 4)
      if len(bits) != 5:
        return
      _, platform, cpu_arch, debug_id, filename = bits
      store_path = os.path.join(output_directory, filename, debug_id)
      if os.path.exists(store_path):
        return
      os.makedirs(store_path)
      if verbose:
        sys.stdout.write("Processing %s [%s]...\n" % (path, arch))
      output_filename = os.path.join(store_path, filename + ".sym")
      f = open(output_filename, "w")
      f.write(stdout)
      f.close()
      return output_filename

    if should_process(fullpath):
      for arch in get_archs(fullpath):
        if arch == "x86_64":
          return process_file(fullpath, arch, False)
    return None

  def symbolicate_profile(self, profile_json):
    if "libs" not in profile_json:
      return
    shared_libraries = json.loads(profile_json["libs"])
    shared_libraries.sort(key=lambda lib: lib["start"])
    addresses = self._find_addresses(profile_json)
    symbols_to_resolve = self._assign_symbols_to_libraries(addresses, shared_libraries)
    symbolication_table = self._resolve_symbols(symbols_to_resolve)
    self._substitute_symbols(profile_json, symbolication_table)

  def _find_addresses(self, profile_json):
    addresses = set()
    for thread in profile_json["threads"]:
      for sample in thread["samples"]:
        for frame in sample["frames"]:
          if frame["location"][0:2] == "0x":
            addresses.add(frame["location"])
          if "lr" in frame and frame["lr"][0:2] == "0x":
            addresses.add(frame["lr"])
    return addresses

  def _get_containing_library(self, address, libs):
    left = 0
    right = len(libs) - 1
    while left <= right:
      mid = (left + right) / 2
      if address >= libs[mid]["end"]:
        left = mid + 1
      elif address < libs[mid]["start"]:
        right = mid - 1
      else:
        return libs[mid]
    return None

  def _assign_symbols_to_libraries(self, addresses, shared_libraries):
    libs_with_symbols = {}
    for address in addresses:
      lib = self._get_containing_library(int(address, 0), shared_libraries)
      if not lib:
        continue
      if lib["start"] not in libs_with_symbols:
        libs_with_symbols[lib["start"]] = { "library": lib, "symbols": set() }
      libs_with_symbols[lib["start"]]["symbols"].add(address)
    return libs_with_symbols.values()

  def _module_from_lib(self, lib):
    if "breakpadId" in lib:
      return [lib["name"].split("/")[-1], lib["breakpadId"]]
    pdbSig = re.sub("[{}\-]", "", lib["pdbSignature"])
    return [lib["pdbName"], pdbSig + lib["pdbAge"]]

  def _resolve_symbols(self, symbols_to_resolve):
    memoryMap = []
    processedStack = []
    all_symbols = []
    for moduleIndex, library_with_symbols in enumerate(symbols_to_resolve):
      lib = library_with_symbols["library"]
      symbols = library_with_symbols["symbols"]
      memoryMap.append(self._module_from_lib(lib))
      all_symbols += symbols
      for symbol in symbols:
        processedStack.append([moduleIndex, int(symbol, 0) - lib["start"]])

    rawRequest = { "stacks": [processedStack], "memoryMap": memoryMap, "version": 4, "symbolSources": ["FIREFOX", "WINDOWS"] }
    request = SymbolicationRequest(self.sym_file_manager, rawRequest)
    if not request.isValidRequest:
      return {}
    symbolicated_stack = request.Symbolicate(0)
    return dict(zip(all_symbols, symbolicated_stack))

  def _substitute_symbols(self, profile_json, symbolication_table):
    for thread in profile_json["threads"]:
      for sample in thread["samples"]:
        for frame in sample["frames"]:
          frame["location"] = symbolication_table.get(frame["location"], frame["location"])
