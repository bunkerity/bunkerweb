(function() { // don't leak XSSTripwire into global ns

  /*
  Assumptions:
    - we need to run first, before any other attacker script
    - we can't prevent tripwire from being detected (e.g. by side effects)
  Todo:
    - a lot more in lockdown
    - protect XHR
  */
  var XSSTripwire = new Object();

  XSSTripwire.report = function() {
    // Notify server
    var notify = XSSTripwire.newXHR();

    // Create a results string to send back
    var results;
    try {
      results = "HTML=" + encodeURIComponent(document.body.outerHTML);
    } catch (e) {} // we don't always have document.body

    notify.open("POST", XSSTripwire.ReportURL, true);
    notify.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
    notify.send(results);
  }

  XSSTripwire.lockdown = function(obj, name) {
    if (Object.defineProperty) {
      Object.defineProperty(obj, name, {
        configurable: false
      })
    }
  }

  XSSTripwire.newXHR = function() {
    var xmlreq = false;
    if (window.XMLHttpRequest) {
      xmlreq = new XMLHttpRequest();
    } else if (window.ActiveXObject) {
      // Try ActiveX
      try {
        xmlreq = new ActiveXObject("Msxml2.XMLHTTP");
      } catch (e1) {
        // first method failed
        try {
          xmlreq = new ActiveXObject("Microsoft.XMLHTTP");
        } catch (e2) {
          // both methods failed
        }
      }
    }
    return xmlreq;
  };

  XSSTripwire.proxy = function(obj, name, report_function_name, exec_original) {
    var proxy = obj[name];
    obj[name] = function() {
      // URL of the page to notify, in the event of a detected XSS event:
      XSSTripwire.ReportURL = "xss-tripwire-report?function=" + encodeURIComponent(report_function_name);

      XSSTripwire.report();

      if (exec_original) {
        return proxy.apply(this, arguments);
      }
    };
    XSSTripwire.lockdown(obj, name);
  };

  XSSTripwire.proxy(window, 'alert', 'window.alert', true);
  XSSTripwire.proxy(window, 'confirm', 'window.confirm', true);
  XSSTripwire.proxy(window, 'prompt', 'window.prompt', true);
  XSSTripwire.proxy(window, 'unescape', 'unescape', true);
  XSSTripwire.proxy(document, 'write', 'document.write', true);
  XSSTripwire.proxy(String, 'fromCharCode', 'String.fromCharCode', true);

})();
