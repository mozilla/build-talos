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
        return null;
      
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
   
    var file = Cc["@mozilla.org/file/directory_service;1"].
                     getService(Ci.nsIProperties).
                     get("TmpD", Ci.nsIFile);
    file.append("results.html");
    file.createUnique(Ci.nsIFile.NORMAL_FILE_TYPE, 0666);
    var foStream = Cc["@mozilla.org/network/file-output-stream;1"].
                         createInstance(Ci.nsIFileOutputStream);
    foStream.init(file, 0x02 | 0x08 | 0x20, 0666, 0); 
    let str = "<html><body><div style='width:80%'>"
      +"<br>\nversion: "+navigator.userAgent
      +"<br>\ndate: "+new Date()
      +"<br>\npan time: "+this.pantime
      +"<br>\npan distance: "+Math.ceil(this.pandistance) + " screen pixels"
      +"<br>\npan lag: " + pretty_array(this.panlag)
      +"<br>\nload lag: " + pretty_array(this.loadlag)
      +"<br>\nzoomin lag: " + pretty_array(this.zoominlag)
      +"</div></body></html>";

    if (this.talos == true) {
      var tpan = "";
      if (pretty_array(this.panlag) == null) {
        tpan = "__start_report" + median_array(this.zoominlag) + "__end_report";
      }
      else {
        tpan = "__start_report" + this.pantime + "__end_report";
      }
      var now = (new Date()).getTime();
      tpan += "__startTimestamp" + now + "__endTimestamp\n";
      dump(tpan);
      
      goQuitApplication();
      window.close();
    }

    foStream.write(str, str.length);
    foStream.close();
    return "file://"+file.path;
  },

  setTalos: function() {
    this.talos = true;
  } 


};
