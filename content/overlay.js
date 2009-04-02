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
    var file = Cc["@mozilla.org/file/directory_service;1"].
                     getService(Ci.nsIProperties).
                     get("TmpD", Ci.nsIFile);
    file.append("results.html");
    file.createUnique(Ci.nsIFile.NORMAL_FILE_TYPE, 0666);
    var foStream = Cc["@mozilla.org/network/file-output-stream;1"].
                         createInstance(Ci.nsIFileOutputStream);
    foStream.init(file, 0x02 | 0x08 | 0x20, 0666, 0); 
    let str = "<html><body><div style='width:80%'>pan time :"+this.pantime
      + "<br>\npan distance: "+this.pandistance
      +"<br>\npan lag: " + this.panlag
      +"<br>\nload lag: " + this.loadlag+"</div></body></html>";
    foStream.write(str, str.length);
    foStream.close();
    return "file://"+file.path;
  }
};


function PanDown(fe) {
  this._fe = fe;
}

PanDown.prototype = {
  go: function() {
    let startTime = new Date();
    let cwu = Browser._windowUtils;
    let cb = Browser._canvasBrowser;
    //    cb.zoomLevel = 2;
    let pageH = cb._contentAreaDimensions[1];        
    let from = window.innerHeight-1;
    let to = 1;
    let step = 15;
    let x = window.innerWidth/2;
    let r = this._fe.report;
    r.pandistance = cb._pageToScreen(pageH);
    function pan () {
      cwu.sendMouseEvent("mousedown", x, from,
                         0, 1, 0, true);
      for (var i = from; i > to;i-=step) {
        cwu.sendMouseEvent("mousemove", x, i,
                           0, 1, 0, true);
      }
      
      let before = new Date();
      cwu.sendMouseEvent("mouseup", x, to, 0, 1, 0, true);
      try {
        cwu.sendMouseEvent("click", x, to, 0, 1, 0, true);
      } catch (ex) {
        dump("ex:"+ex+"\n");
      }
      let delay = new Date() - before;
      r.panlag.push(delay);
      let timeToDelay = Math.max(0, 200 - delay);
      let viewBottom = cb._visibleBounds.bottom;
      dump([pageH, viewBottom, timeToDelay]+" pageH, viewBottom, timeToPan\n");
      if (pageH > viewBottom) {
        setTimeout(pan, timeToDelay, this);
      } else {
        r.pantime = new Date() - startTime;;
        Browser.addTab(r.save(), true);
      }
    }
    pan();
  }
}

function LagDuringLoad(fe) {
  //benchmark controller
  this._fe = fe;
}

LagDuringLoad.prototype = {
  _timeoutDelay: 100,
  
  scheduleNextEvent: function() {
    let self = this;
    function timeout() {
      let diff = (new Date() - self._beforeTimeout) - self._timeoutDelay;
      dump("scheduleNextEvent:"+diff+"\n")
      self._fe.report.loadlag.push(diff);
      self.scheduleNextEvent();
    }
    if (Browser.selectedTab.isLoading()) {
      this._beforeTimeout = new Date()
      this._timeout = setTimeout(timeout, this._timeoutDelay);
    } else {
      //done with loading
      setTimeout(function() {self._fe.nextTest()}, 10000);
    }
  },
  
  go: function () {
    let browser = Browser.selectedBrowser;
    let self = this;
    
    function dummy() {
    }
  
    browser.loadURI("http://wsj.com", null, null, false);
    self.scheduleNextEvent();
  }
}

var BenchFE = {
  currentTest:-1,
  tests:[LagDuringLoad, PanDown],
  report:new Report(),
  
  nextTest : function(aEvent) {
    this.currentTest++;
    if (this.currentTest < this.tests.length) {
      (new this.tests[this.currentTest](this)).go();
    }
  }
};
