# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json

def compress_profile(profile):
  symbols = set()
  for thread in profile["threads"]:
    for sample in thread["samples"]:
      for frame in sample["frames"]:
        if isinstance(frame, basestring):
          symbols.add(frame)
        else:
          symbols.add(frame["location"])
  location_to_index = dict((l, str(i)) for i, l in enumerate(symbols))
  for thread in profile["threads"]:
    for sample in thread["samples"]:
      for i, frame in enumerate(sample["frames"]):
        if isinstance(frame, basestring):
          sample["frames"][i] = location_to_index[frame]
        else:
          frame["location"] = location_to_index[frame["location"]]
  profile["format"] = "profileJSONWithSymbolicationTable,1"
  profile["symbolicationTable"] = dict(enumerate(symbols))
  profile["profileJSON"] = { "threads": profile["threads"] }
  del profile["threads"]

def save_profile(profile, filename):
  f = open(filename, "w")
  json.dump(profile, f)
  f.close()
