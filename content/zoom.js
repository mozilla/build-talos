function Zoom(fe) {
  this._fe = fe;
  this._initialZoomLevel = getBrowser().scale;
}

Zoom.prototype = {
  go: function() {
    addEventListener("ZoomChanged", zoomEvent, false);
    let toX = window.innerWidth-1;
    let toY = window.innerHeight-1;
    this._x = 1;
    this._y = 200;
    this._stepsLeft = 20;
    this._stepX = (toX - this._x)/this._stepsLeft;
    this._stepY = (toY - this._y)/this._stepsLeft;
    this._oldZoom = 0;
    this._startTime = 0;
    this.nextStep();
  },

  click: function(x,y) {
    let cwu = Browser.windowUtils;
    cwu.sendMouseEvent("mousedown", x, y,
                       0, 1, 0, true);
    cwu.sendMouseEvent("mousemove", x, y,
                       0, 1, 0, true);
    cwu.sendMouseEvent("mouseup", x, y,
                       0, 1, 0, true);
  },
    
  nextStep: function () {
    this._startTime = new Date();
    this._oldZoom = getBrowser().scale;
    this.click(this._x, this._y);
    this.click(this._x, this._y);
    setTimeout(function() {self.zoomEvent()}, 10000);
    //zoomEvent should be called?  hmm, how to time this out?    
  }
}

function zoomEvent() {
  let zoom = BenchFE._test;
  let r = zoom._fe.report;
  let self = zoom;

  //only report successful zoom changes
  if (zoom._oldZoom != getBrowser().scale && zoom._startTime > 0) {
    let diff = new Date() - zoom._startTime;
    r.zoominlag.push(diff);
  }
  zoom._stepsLeft--;
  if (zoom._stepsLeft > 0) {
    zoom._x += zoom._stepX;
    zoom._y += zoom._stepY;
    setTimeout(function() {self.nextStep()}, 1000);
  } else {
    getBrowser().scale = zoom._zoomLevel;
    Browser.scrollContentToTop();
    removeEventListener("ZoomChanged", zoom.zoomEvent, false);
    setTimeout(function() {self._fe.nextTest()}, 1000);
  }

  zoom._startTime = 0;
  zoom._oldZoom = 0;
}

