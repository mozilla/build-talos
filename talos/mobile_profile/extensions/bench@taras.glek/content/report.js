function Report() {
  // how long it takes for individual mousemove/mousedowns to occur
  this.panlag = [];
  // how long it takes to pan down a page
  this.pantime = undefined;
  // the height of the page in screen pixels
  this.pandistance = undefined;
  //lag during pageloads
  this.loadlag = [];
  //zoomin lag
  this.zoominlag = [];

  //for use in the talos performance framework
  this.talos = false;
}

Report.prototype = {

  save: function() {
    function pretty_array(inls) {
      if (!inls.length)
        return 0;
      
      var ls = inls.slice(0);
      ls.sort(function (x,y){return x-y});
      var min = ls[0]
      var max = ls[ls.length - 1]
      let mid = ls.length/2;
      let median = ls.length % 2 == 1 ? ls[Math.floor(mid)] : 
        (ls[mid-1]+ls[mid])/2;
      function sum(ret, x) {
        return ret + x
      }
      function subsq(x) {
        let diff = x-avg;
        return diff*diff
      }
      let avg = ls.reduce(sum, 0)/ls.length
      let stdev = Math.round(Math.sqrt(ls.map(subsq).reduce(sum)/ls.length))
      return "(min/median/max/dev) ("+min+"/"+median+"/"+max+"/"+stdev+") "+inls.join(", ")
    }

    function median_array(inls) {
      if (!inls.length)
        return null;

      var ls = inls.slice(0);
      ls.sort(function (x,y){return x-y});
      var mid = ls.length/2;
      var median = ls.length % 2 == 1 ? ls[Math.floor(mid)] : (ls[mid-1]+ls[mid])/2;
      return median;
    }
    
    function writeFile(filename, msg) {
      var FOSTREAM_CID = "@mozilla.org/network/file-output-stream;1";
      var LF_CID = "@mozilla.org/file/local;1";
      var PR_WRITE_ONLY   = 0x02;
      var PR_CREATE_FILE  = 0x08;
      var PR_TRUNCATE     = 0x20;

      var lFile = Cc[LF_CID].createInstance(Ci.nsILocalFile);
      lFile.initWithPath(filename);

      var foStream = Cc[FOSTREAM_CID].createInstance(Ci.nsIFileOutputStream);
      foStream.init(lFile, PR_WRITE_ONLY | PR_CREATE_FILE | PR_TRUNCATE,
                                       0664, 0);

      foStream.write(msg, msg.length);
      foStream.close();
      
      foStream = null;
      lFile = null;
    }
    
    function dumpLog(msg) {
      var logFile = null;
      if (msg.length <= 0)
        return;
      
      try {
        var prefs = Cc['@mozilla.org/preferences-service;1']
          .getService(Ci.nsIPrefBranch2);
        logFile = prefs.getCharPref("talos.logfile");
      } catch(ex) {} //preference is not set, only dump
      if (logFile != null && logFile != '') {
        writeFile(logFile, msg);
      }
      dump(msg);
    }

    if (this.talos == true) {

      var tpan = "";
      if (this.zoominlag.length > 0) {
        tpan = "__start_report" + median_array(this.zoominlag) + "__end_report\n";
      }
      else {
        tpan = "__start_report" + this.pantime + "__end_report\n";
      }
      var now = (new Date()).getTime();
      tpan += "__startTimestamp" + now + "__endTimestamp\n";
      dumpLog(tpan);
      goQuitApplication();
    } else { 
      var file = Cc["@mozilla.org/file/directory_service;1"].
                       getService(Ci.nsIProperties).
                       get("TmpD", Ci.nsIFile);
      file.append("results.html");

      let str = "<html><body><div style='width:80%'>"
        +"<br>\nversion: "+navigator.userAgent
        +"<br>\ndate: "+new Date()
        +"<br>\npan time: "+this.pantime
        +"<br>\npan distance: "+Math.ceil(this.pandistance) + " screen pixels"
        +"<br>\npan lag: " + pretty_array(this.panlag)
        +"<br>\nload lag: " + pretty_array(this.loadlag)
        +"<br>\nzoomin lag: " + pretty_array(this.zoominlag)
        +"</div></body></html>";
      writeFile(file.path, str);
      return "file://"+file.path;
    }

  },

  setTalos: function() {
    this.talos = true;
  } 


};
