gAccRetrieval = 0;

// Detect if we are on older branches that don't have specialpowers enabled talos available
var useSpecialPowers = true;
try {
  if (SpecialPowers === undefined)
    useSpecialPowers = false;
} catch (ex) {
  useSpecialPowers = false;
}

// Make sure not to touch Components before potentially invoking enablePrivilege,
// because otherwise it won't be there.
if (useSpecialPowers) {
  nsIAccessible = SpecialPowers.Ci.nsIAccessible;
  nsIDOMNode = SpecialPowers.Ci.nsIDOMNode;
} else {
  netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
  nsIAccessible = Components.interfaces.nsIAccessible;
  nsIDOMNode = Components.interfaces.nsIDOMNode;
}

function initAccessibility()
{
  if (useSpecialPowers)
    return SpecialPowers.isAccessible();

  netscape.security.PrivilegeManager.enablePrivilege("UniversalXPConnect");
  if (!gAccRetrieval) {
    var retrieval = Components.classes["@mozilla.org/accessibleRetrieval;1"];
    if (retrieval) { // fails if build lacks accessibility module
      gAccRetrieval =
      Components.classes["@mozilla.org/accessibleRetrieval;1"]
                .getService(Components.interfaces.nsIAccessibleRetrieval);
    }
  }
  return gAccRetrieval;
}

function getAccessible(aAccOrElmOrID, aInterfaces)
{
  if (!aAccOrElmOrID) {
    return null;
  }

  var elm = null;

  if (aAccOrElmOrID instanceof nsIAccessible) {
    elm = aAccOrElmOrID.DOMNode;

  } else if (aAccOrElmOrID instanceof nsIDOMNode) {
    elm = aAccOrElmOrID;

  } else {
    elm = document.getElementById(aAccOrElmOrID);
  }

  var acc = (aAccOrElmOrID instanceof nsIAccessible) ? aAccOrElmOrID : null;
  if (!acc) {
    try {
      acc = gAccRetrieval.getAccessibleFor(elm);
    } catch (e) {
    }
  }

  if (!aInterfaces) {
    return acc;
  }

  if (aInterfaces instanceof Array) {
    for (var index = 0; index < aInterfaces.length; index++) {
      try {
        acc.QueryInterface(aInterfaces[index]);
      } catch (e) {
      }
    }
    return acc;
  }
  
  try {
    acc.QueryInterface(aInterfaces);
  } catch (e) {
  }
  
  return acc;
}

// Walk accessible tree of the given identifier to ensure tree creation
function ensureAccessibleTree(aAccOrElmOrID)
{
  var acc;
  if (useSpecialPowers) {
    acc = SpecialPowers.getAccessible(window, aAccOrElmOrID);
  } else {
    oacc = getAccessible(aAccOrElmOrID);
  }
  if (!acc) {
    return;
  }

  var child = acc.firstChild;
  while (child) {
    ensureAccessibleTree(child);
    try {
      child = child.nextSibling;
    } catch (e) {
      child = null;
    }
  }
}
