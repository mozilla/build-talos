var BenchFE = {
  currentTest:-1,
  tests: [LagDuringLoad, Zoom, PanDown],
  report: new Report(),
  talos: false,
  webServer: "locahost",
  
  nextTest : function(aEvent) {
    try {
    this.currentTest++;
    if (this.currentTest < this.tests.length) {
      (new this.tests[this.currentTest](this)).go();
    } else {
      Browser.addTab(this.report.save(), true);
      this._currentTest = -1;
      this.report = new Report();
    }
    } catch (x) {
      dump(x + "\n" + x.stack + "\n")
    }
  }
};

/*
  NOTE: need to load page, so calling LagDuringLoad for each test set.
        We are not testing this as it is covered in page_load_test
*/

var myExtension = {
  myListener: function(evt) {
    BenchFE.talos = true;
    BenchFE.report.setTalos();
    var test = evt.target.getAttribute("attribute1");
    BenchFE.webServer = evt.target.getAttribute("webServer");
    if (BenchFE.webServer == null) {
      BenchFE.webServer = "localhost";
    }
    if (test == "Zoom") { BenchFE.tests = [LagDuringLoad, Zoom]; };
    if (test == "PanDown") { BenchFE.tests = [LagDuringLoad, PanDown]; };

    setTimeout(function() {BenchFE.nextTest(); }, 3000);
  }
}

document.addEventListener("myExtensionEvent", function (e) { myExtension.myListener(e); }, false, true);

