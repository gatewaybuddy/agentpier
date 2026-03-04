/**
 * AgentPier Trust Badge Widget v1
 *
 * Usage:
 *   <div class="agentpier-badge" data-agent-id="agent-123" data-style="compact"></div>
 *   <script src="https://api.agentpier.org/static/widget-v1.js"></script>
 */
(function () {
  "use strict";

  var API_BASE = "https://api.agentpier.org";
  var FALLBACK_TEXT = "Trust Score Unavailable";

  function fetchBadge(agentId, style, container) {
    var url = API_BASE + "/badges/" + encodeURIComponent(agentId) + "/image";
    if (style) {
      url += "?style=" + encodeURIComponent(style);
    }

    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      if (xhr.status === 200) {
        container.innerHTML = xhr.responseText;
      } else {
        container.textContent = FALLBACK_TEXT;
      }
    };
    xhr.onerror = function () {
      container.textContent = FALLBACK_TEXT;
    };
    xhr.send();
  }

  function init() {
    var badges = document.querySelectorAll(".agentpier-badge");
    for (var i = 0; i < badges.length; i++) {
      var el = badges[i];
      var agentId = el.getAttribute("data-agent-id");
      var style = el.getAttribute("data-style") || "compact";
      if (agentId) {
        fetchBadge(agentId, style, el);
      } else {
        el.textContent = FALLBACK_TEXT;
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
