import { render } from "preact";
import { ChatAPI } from "./api";
import { Widget } from "./Widget";
import "./styles.css";

/**
 * Entry point for the chat widget.
 *
 * Reads channel_id from the URL query string and initializes the ChatAPI.
 * When loaded inside an iframe (via embed.js), the URL looks like:
 *   /index.html?channel_id=<uuid>
 */
function bootstrap() {
  const params = new URLSearchParams(window.location.search);
  const channelId = params.get("channel_id") || "";

  // Determine API URL: same origin as the widget, or configurable
  const apiUrl =
    params.get("api_url") ||
    window.location.origin.replace(/:3001$/, ":8000");

  const api = new ChatAPI(channelId, apiUrl);

  const root = document.getElementById("widget-root");
  if (root) {
    render(<Widget api={api} />, root);
  }
}

bootstrap();
