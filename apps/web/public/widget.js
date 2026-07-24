/**
 * F12 Embed Widget — float panel loader.
 * API base = origin of this script (tenant host) + /backend/v1/widget/...
 * Browser holds only pk_ site key (never server API keys).
 */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) {
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      if ((scripts[i].src || "").indexOf("/widget.js") !== -1) {
        script = scripts[i];
        break;
      }
    }
  }
  if (!script) return;

  var siteKey = script.getAttribute("data-site-key") || "";
  if (!siteKey) {
    console.warn("[lxzxai-widget] missing data-site-key");
    return;
  }

  var themeColor = script.getAttribute("data-theme-color") || "#20b898";
  var welcome =
    script.getAttribute("data-welcome") || "你好，有什么可以帮你的？";
  var startOpen = (script.getAttribute("data-open") || "false") === "true";

  var scriptUrl;
  try {
    scriptUrl = new URL(script.src, window.location.href);
  } catch (e) {
    console.warn("[lxzxai-widget] invalid script src");
    return;
  }
  var apiBase = scriptUrl.origin + "/backend/v1/widget";

  var conversationId = null;
  var open = startOpen;
  var sending = false;

  var root = document.createElement("div");
  root.id = "lxzxai-widget-root";
  root.setAttribute("data-lxzxai-widget", "1");

  var style = document.createElement("style");
  style.textContent =
    "#lxzxai-widget-root{all:initial;font-family:Segoe UI,SF Pro Text,PingFang SC,Hiragino Sans GB,Microsoft YaHei,system-ui,sans-serif;}" +
    "#lxzxai-widget-root *{box-sizing:border-box;}" +
    "#lxzxai-widget-launcher{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:52px;height:52px;border-radius:50%;border:none;cursor:pointer;background:" +
    themeColor +
    ";color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.18);font-size:22px;line-height:1;}" +
    "#lxzxai-widget-panel{position:fixed;right:20px;bottom:84px;z-index:2147483000;width:min(360px,calc(100vw - 24px));height:min(520px,calc(100vh - 120px));display:none;flex-direction:column;background:#fff;border:1px solid #e2e4e8;border-radius:16px;box-shadow:0 16px 40px rgba(0,0,0,.16);overflow:hidden;}" +
    "#lxzxai-widget-panel.open{display:flex;}" +
    "#lxzxai-widget-header{padding:12px 14px;background:" +
    themeColor +
    ";color:#fff;font-size:14px;font-weight:600;display:flex;justify-content:space-between;align-items:center;}" +
    "#lxzxai-widget-close{border:none;background:transparent;color:#fff;cursor:pointer;font-size:18px;line-height:1;}" +
    "#lxzxai-widget-messages{flex:1;overflow:auto;padding:12px;background:#f7f8fa;}" +
    "#lxzxai-widget-messages .msg{margin:0 0 10px;padding:8px 10px;border-radius:10px;font-size:13px;line-height:1.45;max-width:92%;white-space:pre-wrap;word-break:break-word;}" +
    "#lxzxai-widget-messages .msg.user{margin-left:auto;background:#eef1f4;color:#1a1d21;}" +
    "#lxzxai-widget-messages .msg.assistant{margin-right:auto;background:#fff;border:1px solid #e2e4e8;color:#1a1d21;}" +
    "#lxzxai-widget-messages .msg.system{margin:0 auto 12px;background:transparent;color:#8a919c;font-size:12px;text-align:center;}" +
    "#lxzxai-widget-form{display:flex;gap:8px;padding:10px;border-top:1px solid #e2e4e8;background:#fff;}" +
    "#lxzxai-widget-input{flex:1;border:1px solid #cfd3da;border-radius:8px;padding:8px 10px;font:inherit;font-size:13px;resize:none;min-height:38px;max-height:96px;}" +
    "#lxzxai-widget-send{border:none;border-radius:8px;padding:0 12px;background:" +
    themeColor +
    ";color:#fff;cursor:pointer;font-size:13px;font-weight:600;}" +
    "#lxzxai-widget-send:disabled{opacity:.55;cursor:not-allowed;}";

  var launcher = document.createElement("button");
  launcher.id = "lxzxai-widget-launcher";
  launcher.type = "button";
  launcher.setAttribute("aria-label", "打开客服");
  launcher.textContent = "💬";

  var panel = document.createElement("div");
  panel.id = "lxzxai-widget-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "知识库助手");

  var header = document.createElement("div");
  header.id = "lxzxai-widget-header";
  header.innerHTML =
    "<span>知识库助手</span><button type=\"button\" id=\"lxzxai-widget-close\" aria-label=\"关闭\">×</button>";

  var messages = document.createElement("div");
  messages.id = "lxzxai-widget-messages";

  var form = document.createElement("form");
  form.id = "lxzxai-widget-form";
  form.innerHTML =
    '<textarea id="lxzxai-widget-input" rows="1" placeholder="输入问题…"></textarea>' +
    '<button id="lxzxai-widget-send" type="submit">发送</button>';

  panel.appendChild(header);
  panel.appendChild(messages);
  panel.appendChild(form);
  root.appendChild(style);
  root.appendChild(panel);
  root.appendChild(launcher);
  document.body.appendChild(root);

  function addMsg(role, text) {
    var el = document.createElement("div");
    el.className = "msg " + role;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  addMsg("system", welcome);

  function setOpen(next) {
    open = next;
    if (open) panel.classList.add("open");
    else panel.classList.remove("open");
  }

  launcher.addEventListener("click", function () {
    setOpen(!open);
  });
  header.querySelector("#lxzxai-widget-close").addEventListener("click", function () {
    setOpen(false);
  });
  setOpen(startOpen);

  function parseSseChunk(raw) {
    var event = "";
    var dataLines = [];
    var lines = raw.split("\n");
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.indexOf("event:") === 0) {
        event = line.slice(6).trim();
      } else if (line.indexOf("data:") === 0) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (!event || dataLines.length === 0) return null;
    try {
      return { event: event, data: JSON.parse(dataLines.join("\n")) };
    } catch (e) {
      return null;
    }
  }

  function readErrorBody(res) {
    return res.text().then(function (text) {
      if (!text) return res.statusText || "request failed";
      try {
        var data = JSON.parse(text);
        var detail = data && data.detail;
        if (typeof detail === "string") return detail;
        if (detail) return JSON.stringify(detail);
      } catch (e) {
        /* plain text / HTML proxy error */
      }
      var snip = text.replace(/\s+/g, " ").trim().slice(0, 160);
      return snip || res.statusText || "request failed";
    });
  }

  /** Prefer SSE so long agent turns (LLM retries) don't hit rewrite/proxy idle timeouts. */
  function chatStream(body) {
    return fetch(apiBase + "/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Site-Key": siteKey,
      },
      body: JSON.stringify(body || {}),
    }).then(function (res) {
      if (!res.ok || !res.body) {
        return readErrorBody(res).then(function (msg) {
          throw new Error(msg);
        });
      }
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var doneTurn = null;

      function pump() {
        return reader.read().then(function (result) {
          if (result.done) {
            if (!doneTurn) throw new Error("stream finished without done event");
            return doneTurn;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (var i = 0; i < parts.length; i++) {
            var parsed = parseSseChunk(parts[i]);
            if (!parsed) continue;
            if (parsed.event === "started" && parsed.data.conversation_id) {
              conversationId = parsed.data.conversation_id;
            } else if (parsed.event === "done") {
              doneTurn = parsed.data;
            } else if (parsed.event === "error") {
              throw new Error(
                (parsed.data && parsed.data.message) || "streaming failed",
              );
            }
          }
          return pump();
        });
      }
      return pump();
    });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (sending) return;
    var input = form.querySelector("#lxzxai-widget-input");
    var text = (input.value || "").trim();
    if (!text) return;
    input.value = "";
    addMsg("user", text);
    var pending = addMsg("assistant", "思考中…");
    sending = true;
    form.querySelector("#lxzxai-widget-send").disabled = true;

    var payload = { content: text };
    if (conversationId) payload.conversation_id = conversationId;

    chatStream(payload)
      .then(function (data) {
        if (data.conversation_id) conversationId = data.conversation_id;
        pending.textContent =
          (data.assistant && data.assistant.content) || "（无回复）";
      })
      .catch(function (err) {
        pending.textContent = "发送失败：" + (err.message || String(err));
      })
      .then(function () {
        sending = false;
        form.querySelector("#lxzxai-widget-send").disabled = false;
        messages.scrollTop = messages.scrollHeight;
      });
  });
})();
