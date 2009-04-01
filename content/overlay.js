//alert("foofa")
var Sample = {
  
  onLoad : function() {
		/* do something when the browser window loads */
  },

  doIt : function(aEvent) {
    let startTime = new Date();
    let cwu = Browser._windowUtils;
    let cb = Browser._canvasBrowser;
//    cb.zoomLevel = 2;
    let pageH = cb._contentAreaDimensions[1];        
    let from = window.innerHeight-1;
    let to = 1;
    let step = 15;
    let delays = [];
    let x = window.innerWidth/2;
    
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
      delays.push(delay);
      let timeToDelay = Math.max(0, 200 - delay);
      let viewBottom = cb._visibleBounds.bottom;
      dump([pageH, viewBottom, timeToDelay]+" pageH, viewBottom, timeToPan\n");
      if (pageH > viewBottom) {
        dump("going again\n");
        setTimeout(pan, timeToDelay, this);
      } else {
        let timeTaken = new Date() - startTime;
         alert("Full pan took "+timeTaken+"ms delays:"+delays)//15601ms
      }
    }
    pan();
  }
};

window.addEventListener("load", function(e) { Sample.onLoad(e); }, false);

