/* -*- Mode: C++; tab-width: 20; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is tp.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2007
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *   Darin Fisher <darin@meer.net>
 *   Rob Helmer <rhelmer@mozilla.com>
 *   Vladimir Vukicevic <vladimir@mozilla.com>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

// Constructor
function Report(pages) {
  this.pages = pages;
  this.timeVals = new Array(pages.length);  // matrix of times
  for (var i = 0; i < this.timeVals.length; ++i) {
    this.timeVals[i] = new Array();
  }
  this.totalCCTime = 0;
  this.showTotalCCTime = false;
}

// given an array of strings, finds the longest common prefix
function findCommonPrefixLength(strs) {
  if (strs.length < 2)
    return 0;

  var len = 0;
  do {
    var newlen = len + 1;
    var newprefix = null;
    var failed = false;
    for (var i = 0; i < strs.length; i++) {
      if (newlen > strs[i].length) {
	failed = true;
	break;
      }

      var s = strs[i].substr(0, newlen);
      if (newprefix == null) {
	newprefix = s;
      } else if (newprefix != s) {
	failed = true;
	break;
      }
    }

    if (failed)
      break;

    len++;
  } while (true);
  return len;
}

function strPad(o, len, left) {
  var str = o.toString();
  if (!len)
    len = 6;
  if (left == null)
    left = true;

  if (str.length < len) {
    len -= str.length;
    while (--len) {
      if (left) {
        str = " " + str;
      } else {
        str += " ";
      }
    }
  }

  str += " ";
  return str;
}

function strPadFixed(n, len, left) {
  return strPad(n.toFixed(0), len, left);
}

Report.prototype.getReport = function(format) {

  var report;
  var prefixLen = findCommonPrefixLength(this.pages);

  if (format == "text") {
    // output text format suitable for dumping
    report = "============================================================\n";
    report += "    " + strPad("Page", 40, false) + "raw" + "\n";
    for (var i = 0; i < this.timeVals.length; i++) {
      report +=
        strPad(i, 4, true) +
        strPad(this.pages[i].substr(prefixLen), 40, false) +
        this.timeVals[i] +
        "\n";
    }
    if (this.showTotalCCTime) {
      report += "Cycle collection: " + this.totalCCTime + "\n"
    }
    report += "============================================================\n";
  } else if (format == "tinderbox") {
    report = "__start_tp_report\n";
    report += "_x_x_mozilla_page_load\n";
    report += "_x_x_mozilla_page_load_details\n";
    report += "|i|pagename|runs|\n";

    for (var i = 0; i < this.timeVals.length; i++) {
      report += '|'+
        i + ';'+
        this.pages[i].substr(prefixLen) + ';'+
        this.timeVals[i].join(";") +
        "\n";
    }
    report += "__end_tp_report\n";
    if (this.showTotalCCTime) {
      report += "__start_cc_report\n";
      report += "_x_x_mozilla_cycle_collect," + this.totalCCTime + "\n";
      report += "__end_cc_report\n";
    }
    var now = (new Date()).getTime();
    report += "__startTimestamp" + now + "__endTimestamp\n"; //timestamp for determning shutdown time, used by talos
  } else {
    report = "Unknown report format";
  }

  return report;
}

Report.prototype.recordTime = function(pageIndex, ms) {
  this.timeVals[pageIndex].push(ms);
}

Report.prototype.recordCCTime = function(ms) {
  this.totalCCTime += ms;
  this.showTotalCCTime = true;
}
