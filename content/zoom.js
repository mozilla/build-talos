function Zoom(fe) {
  this._fe = fe;
  this._zoomLevel = Browser._canvasBrowser.zoomLevel;
}

Zoom.prototype = {
  go: function() {
    let toX = window.innerWidth-1;
    let toY = window.innerHeight-1;
    this._x = 1;
    this._y = 200;
    this._stepsLeft = 20;
    this._stepX = (toX - this._x)/this._stepsLeft;
    this._stepY = (toY - this._y)/this._stepsLeft;

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
    let r = this._fe.report;
    let startTime = new Date();    
    let cb = Browser._canvasBrowser;
    let oldZoom = cb.zoomLevel;
    let self = this;
    this.click(this._x, this._y);
    this.click(this._x, this._y);
    
    //only report successful zoom changes
    if (oldZoom != cb.zoomLevel)
      r.zoominlag.push(new Date() - startTime);
    this._stepsLeft--;
    if (this._stepsLeft > 0) {
      this._x += this._stepX;
      this._y += this._stepY;
      setTimeout(function() {self.nextStep()}, 1000);
    } else {
      ws.panTo(0,0);
      cb.zoomLevel = this._zoomLevel;
      setTimeout(function() {self._fe.nextTest()}, 1000);
    }
  }
}
