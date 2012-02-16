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
      this._test = (new this.tests[this.currentTest](this));
      this._test.go();
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

function myListener(m) {
  BenchFE.talos = true;
  BenchFE.report.setTalos();
  var test = m.json.test;
  BenchFE.webServer = m.json.webServer;
  if (BenchFE.webServer == null) {
    BenchFE.webServer = "localhost";
  }
  if (test == "Zoom") { BenchFE.tests = [LagDuringLoad, Zoom]; };
  if (test == "PanDown") { BenchFE.tests = [LagDuringLoad, PanDown]; };

  setTimeout(function() {BenchFE.nextTest(); }, 3000);
}

messageManager.addMessageListener("fbChromeEvent", myListener);

