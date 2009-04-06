function Report() {
  // how long it takes for individual mousemove/mousedowns to occur
  this.panlag = [];
  // how long it takes to pan down a page
  this.pantime = undefined;
  // the height of the page in screen pixels
  this.pandistance = undefined;
  //lag during pageloads
  this.loadlag = [];
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
      +"<br>\npan distance: "+Math.ceil(this.pandistance)
      +"<br>\npan lag: " + pretty_array(this.panlag)
      +"<br>\nload lag: " + pretty_array(this.loadlag)
      +"</div></body></html>";
    foStream.write(str, str.length);
    foStream.close();
    return "file://"+file.path;
  }
};
