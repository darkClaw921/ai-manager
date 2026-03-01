/**
 * AI Chat Widget embed loader.
 *
 * Usage:
 *   <script src="https://your-domain.com/widget/embed.js" data-channel-id="uuid"></script>
 *
 * Creates an iframe with the chat widget positioned in the bottom-right corner.
 * Communicates with the iframe via postMessage.
 */
(function () {
  "use strict";

  // Find the current script tag to read data attributes
  var scripts = document.getElementsByTagName("script");
  var currentScript = scripts[scripts.length - 1];
  var channelId = currentScript.getAttribute("data-channel-id");

  if (!channelId) {
    console.error("[AI Widget] data-channel-id attribute is required");
    return;
  }

  // Determine the widget URL from the script src
  var scriptSrc = currentScript.src;
  var widgetBaseUrl = scriptSrc.substring(0, scriptSrc.lastIndexOf("/"));
  var widgetUrl = widgetBaseUrl + "/index.html?channel_id=" + encodeURIComponent(channelId);

  // Default dimensions
  var WIDGET_WIDTH = 400;
  var WIDGET_HEIGHT = 600;
  var WIDGET_BOTTOM = 20;
  var WIDGET_RIGHT = 20;

  // Create iframe
  var iframe = document.createElement("iframe");
  iframe.src = widgetUrl;
  iframe.id = "ai-chat-widget-iframe";
  iframe.style.cssText = [
    "position: fixed",
    "bottom: " + WIDGET_BOTTOM + "px",
    "right: " + WIDGET_RIGHT + "px",
    "width: " + WIDGET_WIDTH + "px",
    "height: " + WIDGET_HEIGHT + "px",
    "border: none",
    "z-index: 999999",
    "background: transparent",
    "border-radius: 16px",
    "box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12)",
    "transition: all 0.3s ease",
    "overflow: hidden",
  ].join("; ");

  // Accessibility
  iframe.setAttribute("title", "AI Chat Widget");
  iframe.setAttribute("allow", "microphone");

  document.body.appendChild(iframe);

  // Listen for messages from the iframe
  window.addEventListener("message", function (event) {
    // Only accept messages from our widget origin
    try {
      var iframeOrigin = new URL(widgetUrl).origin;
      if (event.origin !== iframeOrigin) return;
    } catch (e) {
      return;
    }

    var data = event.data;
    if (!data || !data.type) return;

    switch (data.type) {
      case "widget:resize":
        if (data.width) iframe.style.width = data.width + "px";
        if (data.height) iframe.style.height = data.height + "px";
        break;

      case "widget:close":
        iframe.style.display = "none";
        break;

      case "widget:open":
        iframe.style.display = "block";
        break;

      case "widget:minimize":
        iframe.style.width = "60px";
        iframe.style.height = "60px";
        iframe.style.borderRadius = "50%";
        break;

      case "widget:maximize":
        iframe.style.width = WIDGET_WIDTH + "px";
        iframe.style.height = WIDGET_HEIGHT + "px";
        iframe.style.borderRadius = "16px";
        break;
    }
  });
})();
