#!/usr/bin/env python3
"""Inject per-notebook CPD JupyterHub launch links into built MyST HTML."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


BUILD_DIR = Path("_build/html")
HTML_ENTRYPOINT = "index.html"
HUB_URL = "https://icg-cpd-cluster.port.ac.uk/jupyterhub"
REPO_URL = "https://github.com/xangma/UKSA_SoftwareDataAI_Training"
REPO_DIR = "UKSA_SoftwareDataAI_Training"
BRANCH = "main"
ROOT_PATH = "/jupyterbook"
THEBE_BOOTSTRAP_PATH = "/jupyterhub/services/uksa-thebe/bootstrap"
THEBE_STATUS_PATH = "/jupyterhub/services/uksa-thebe/status"
THEBE_DISCONNECT_PATH = "/jupyterhub/services/uksa-thebe/disconnect"
HUB_HOME_PATH = "/jupyterhub/hub/home"
THEBE_READY_PARAM = "uksa-thebe-ready"
MARKER_START = "<!-- cpd-jupyterhub-launch-links:start -->"
MARKER_END = "<!-- cpd-jupyterhub-launch-links:end -->"


def launch_url(source_path: str | None = None) -> str:
    target = REPO_DIR
    if source_path:
        target = f"{REPO_DIR}/{source_path.strip('/')}"
    query = urlencode(
        {
            "repo": REPO_URL,
            "branch": BRANCH,
            "urlpath": f"lab/tree/{target}?autodecode",
        },
        quote_via=quote,
    )
    return f"{HUB_URL.rstrip('/')}/hub/user-redirect/git-pull?{query}"


def page_path(build_dir: Path, html_path: Path) -> str:
    relative = html_path.relative_to(build_dir)
    root = ROOT_PATH.rstrip("/")
    if relative.name == "index.html":
        suffix = "/".join(relative.parent.parts)
        return f"{root}/{suffix}/" if suffix else f"{root}/"
    suffix = "/".join(relative.with_suffix("").parts)
    return f"{root}/{suffix}"


def bootstrap_url(return_path: str, start_thebe: bool = False) -> str:
    return_target = (
        with_query_params(return_path, {THEBE_READY_PARAM: "1", "thebe": "1"})
        if start_thebe
        else return_path
    )
    params = {"return": return_target}
    if start_thebe:
        params["thebe"] = "1"
    query = urlencode(params, quote_via=quote)
    return f"{THEBE_BOOTSTRAP_PATH}?{query}"


def with_query_params(url: str, params: dict[str, str]) -> str:
    parts = list(urlsplit(url))
    query = [
        (key, value)
        for key, value in parse_qsl(parts[3], keep_blank_values=True)
        if key not in params
    ]
    query.extend(params.items())
    parts[3] = urlencode(query, doseq=True)
    return urlunsplit(parts)


def rewrite_static_connect_urls(html: str, return_path: str) -> str:
    target = bootstrap_url(return_path)
    return re.sub(
        rf"{re.escape(THEBE_BOOTSTRAP_PATH)}(?:\?return=[^\"'<\s]*)?",
        target,
        html,
    )


def extract_project(html_text: str) -> dict:
    marker = '"project":'
    start = html_text.find(marker)
    if start == -1:
        raise ValueError("Could not find MyST project metadata in built HTML")
    project, _ = json.JSONDecoder().raw_decode(html_text[start + len(marker) :])
    if not isinstance(project, dict):
        raise ValueError("MyST project metadata was not a JSON object")
    return project


def iter_visible_files(items: list[dict]) -> list[str]:
    files: list[str] = []
    for item in items:
        if item.get("hidden"):
            continue
        if "file" in item:
            files.append(item["file"])
        files.extend(iter_visible_files(item.get("children", [])))
    return files


def notebook_routes(project: dict) -> dict[str, str]:
    files = [
        file
        for file in iter_visible_files(project.get("toc", []))
        if file != "index.md"
    ]
    pages = [page for page in project.get("pages", []) if "slug" in page]
    if len(files) != len(pages):
        raise ValueError(
            f"Could not align MyST TOC files ({len(files)}) with pages ({len(pages)})"
        )

    routes: dict[str, str] = {}
    for file, page in zip(files, pages):
        if file.endswith(".ipynb"):
            routes[page["slug"]] = launch_url(file)
    return routes


def injected_script(routes: dict[str, str]) -> str:
    routes_json = json.dumps(routes, sort_keys=True, separators=(",", ":"))
    default_url = json.dumps(launch_url())
    root_path = json.dumps(ROOT_PATH.rstrip("/"))
    thebe_bootstrap_path = json.dumps(THEBE_BOOTSTRAP_PATH)
    thebe_status_path = json.dumps(THEBE_STATUS_PATH)
    thebe_disconnect_path = json.dumps(THEBE_DISCONNECT_PATH)
    hub_home_path = json.dumps(HUB_HOME_PATH)
    thebe_ready_param = json.dumps(THEBE_READY_PARAM)
    return f"""{MARKER_START}
<style id="cpd-jupyterhub-launch-link-styles">
.cpd-jupyterhub-menu-wrap {{
  display: inline-flex;
  position: relative;
}}
a.cpd-jupyterhub-connect {{
  align-items: center;
  display: inline-flex;
  gap: 0.45rem;
  white-space: nowrap;
}}
a.cpd-jupyterhub-connect .cpd-jupyterhub-status {{
  background: #6b7280;
  border-radius: 9999px;
  box-shadow: 0 0 0 2px rgba(107, 114, 128, 0.22);
  flex: 0 0 auto;
  height: 0.62rem;
  position: relative;
  width: 0.62rem;
}}
a.cpd-jupyterhub-connect[data-cpd-jupyterhub-state="connected"] .cpd-jupyterhub-status {{
  background: #15803d;
  box-shadow: 0 0 0 2px rgba(21, 128, 61, 0.22);
}}
a.cpd-jupyterhub-connect[data-cpd-jupyterhub-state="connecting"] .cpd-jupyterhub-status {{
  background: #ca8a04;
  box-shadow: 0 0 0 2px rgba(202, 138, 4, 0.22);
}}
a.cpd-jupyterhub-connect[data-cpd-jupyterhub-state="connected"] .cpd-jupyterhub-status::after {{
  border: solid white;
  border-width: 0 0.09rem 0.09rem 0;
  content: "";
  height: 0.34rem;
  left: 0.21rem;
  position: absolute;
  top: 0.08rem;
  transform: rotate(45deg);
  width: 0.18rem;
}}
a.cpd-jupyterhub-connect .cpd-jupyterhub-caret {{
  border: solid currentColor;
  border-width: 0 0.1rem 0.1rem 0;
  display: none;
  height: 0.38rem;
  margin-left: 0.1rem;
  transform: rotate(45deg) translateY(-0.08rem);
  width: 0.38rem;
}}
a.cpd-jupyterhub-connect[data-cpd-jupyterhub-state="connected"] .cpd-jupyterhub-caret {{
  display: inline-block;
}}
.cpd-jupyterhub-menu {{
  background: #ffffff;
  border: 1px solid rgba(120, 113, 108, 0.28);
  border-radius: 0.35rem;
  box-shadow: 0 0.75rem 1.5rem rgba(28, 25, 23, 0.16);
  color: #292524;
  display: none;
  min-width: 13.5rem;
  padding: 0.35rem;
  position: absolute;
  right: 0;
  top: calc(100% + 0.4rem);
  z-index: 60;
}}
.cpd-jupyterhub-menu-wrap[data-cpd-jupyterhub-menu-open="1"] .cpd-jupyterhub-menu {{
  display: block;
}}
.cpd-jupyterhub-menu-user {{
  border-bottom: 1px solid rgba(120, 113, 108, 0.18);
  color: #57534e;
  font-size: 0.78rem;
  margin-bottom: 0.25rem;
  overflow: hidden;
  padding: 0.35rem 0.45rem 0.5rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.cpd-jupyterhub-menu a {{
  border-radius: 0.25rem;
  color: inherit;
  display: block;
  font-size: 0.88rem;
  line-height: 1.35;
  padding: 0.42rem 0.45rem;
  text-decoration: none;
}}
.cpd-jupyterhub-menu a:hover,
.cpd-jupyterhub-menu a:focus {{
  background: #f5f5f4;
  outline: none;
}}
html.dark .cpd-jupyterhub-menu {{
  background: #1c1917;
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 0.75rem 1.5rem rgba(0, 0, 0, 0.4);
  color: #fafaf9;
}}
html.dark .cpd-jupyterhub-menu-user {{
  border-bottom-color: rgba(255, 255, 255, 0.16);
  color: #d6d3d1;
}}
html.dark .cpd-jupyterhub-menu a:hover,
html.dark .cpd-jupyterhub-menu a:focus {{
  background: #44403c;
}}
</style>
<script id="cpd-jupyterhub-launch-links">
(() => {{
  const rootPath = {root_path};
  const defaultUrl = {default_url};
  const thebeBootstrapPath = {thebe_bootstrap_path};
  const thebeStatusPath = {thebe_status_path};
  const thebeDisconnectPath = {thebe_disconnect_path};
  const hubHomePath = {hub_home_path};
  const thebeReadyParam = {thebe_ready_param};
  const notebookUrls = {routes_json};
  let hubConnected = false;
  let hubConnecting = false;
  let hubUser = "";
  let connectMenuCounter = 0;

  function currentReturnPath(options = {{}}) {{
    const url = new URL(window.location.href);
    if (options.clearThebe) {{
      url.searchParams.delete("thebe");
      url.searchParams.delete(thebeReadyParam);
    }}
    if (options.startThebe) {{
      url.searchParams.set("thebe", "1");
      url.searchParams.set(thebeReadyParam, "1");
    }}
    return url.pathname + url.search + url.hash;
  }}

  function currentSlug() {{
    let path = window.location.pathname.replace(/\\/$/, "");
    if (path === rootPath || path === "") return "";
    if (path.startsWith(rootPath + "/")) path = path.slice(rootPath.length + 1);
    return decodeURIComponent(path.replace(/^\\/+/, "").replace(/\\/$/, ""));
  }}

  function currentNotebookUrl() {{
    return notebookUrls[currentSlug()] || "";
  }}

  function bootstrapUrl(returnPath = currentReturnPath(), options = {{}}) {{
    const url = new URL(thebeBootstrapPath, window.location.origin);
    url.searchParams.set("return", returnPath);
    if (options.startThebe) url.searchParams.set("thebe", "1");
    return url.pathname + url.search;
  }}

  function disconnectUrl(returnPath = currentReturnPath({{ clearThebe: true }})) {{
    const url = new URL(thebeDisconnectPath, window.location.origin);
    url.searchParams.set("return", returnPath);
    return url.pathname + url.search;
  }}

  function shouldBootstrapBeforeThebe() {{
    const params = new URLSearchParams(window.location.search);
    return params.get("thebe") === "1" && params.get(thebeReadyParam) !== "1";
  }}

  if (shouldBootstrapBeforeThebe()) {{
    window.location.replace(
      bootstrapUrl(currentReturnPath({{ startThebe: true }}), {{ startThebe: true }})
    );
    return;
  }}

  function connectState() {{
    if (hubConnecting) return "connecting";
    return hubConnected ? "connected" : "disconnected";
  }}

  function connectLabel(state) {{
    if (state === "connected") return "Connected to JupyterHub";
    if (state === "connecting") return "Connecting to JupyterHub";
    return "Connect to JupyterHub";
  }}

  function closeConnectMenus(except = null) {{
    for (const wrapper of document.querySelectorAll(".cpd-jupyterhub-menu-wrap[data-cpd-jupyterhub-menu-open='1']")) {{
      if (wrapper === except) continue;
      setConnectMenuOpen(wrapper, false);
    }}
  }}

  function setConnectMenuOpen(wrapper, open) {{
    const menu = Array.from(wrapper.children).find((child) =>
      child.classList && child.classList.contains("cpd-jupyterhub-menu")
    );
    const link = wrapper.querySelector("a.cpd-jupyterhub-connect");
    if (open) {{
      wrapper.dataset.cpdJupyterhubMenuOpen = "1";
      if (menu) menu.hidden = false;
      if (link) link.setAttribute("aria-expanded", "true");
    }} else {{
      delete wrapper.dataset.cpdJupyterhubMenuOpen;
      if (menu) menu.hidden = true;
      if (link) link.setAttribute("aria-expanded", "false");
    }}
  }}

  function ensureConnectMenu(link) {{
    let wrapper = link.parentElement;
    if (
      !wrapper
      || !wrapper.classList.contains("cpd-jupyterhub-menu-wrap")
      || wrapper.dataset.cpdJupyterhubWrapper !== "1"
    ) {{
      wrapper = document.createElement("span");
      wrapper.className = "cpd-jupyterhub-menu-wrap";
      wrapper.dataset.cpdJupyterhubWrapper = "1";
      link.parentNode.insertBefore(wrapper, link);
      wrapper.appendChild(link);
    }}

    let menu = Array.from(wrapper.children).find((child) =>
      child.classList && child.classList.contains("cpd-jupyterhub-menu")
    );
    if (!link.id) {{
      connectMenuCounter += 1;
      link.id = "cpd-jupyterhub-connect-" + connectMenuCounter;
    }}
    if (!menu) {{
      menu = document.createElement("div");
      menu.className = "cpd-jupyterhub-menu";
      menu.hidden = true;
      menu.setAttribute("role", "menu");
      wrapper.appendChild(menu);
    }}
    if (!menu.id) menu.id = link.id + "-menu";
    menu.setAttribute("aria-labelledby", link.id);

    return {{ wrapper, menu }};
  }}

  function updateConnectMenu(menu) {{
    const disconnectHref = disconnectUrl();
    if (
      menu.dataset.cpdJupyterhubMenuReady === "1"
      && menu.dataset.cpdJupyterhubUser === hubUser
      && menu.dataset.cpdJupyterhubDisconnectHref === disconnectHref
    ) {{
      return;
    }}

    const items = [];
    if (hubUser) {{
      const user = document.createElement("div");
      user.className = "cpd-jupyterhub-menu-user";
      user.textContent = "Signed in as " + hubUser;
      items.push(user);
    }}

    const openHub = document.createElement("a");
    openHub.href = hubHomePath;
    openHub.textContent = "Open JupyterHub";
    openHub.setAttribute("role", "menuitem");
    items.push(openHub);

    const disconnect = document.createElement("a");
    disconnect.href = disconnectHref;
    disconnect.textContent = "Disconnect";
    disconnect.setAttribute("role", "menuitem");
    items.push(disconnect);

    menu.dataset.cpdJupyterhubMenuReady = "1";
    menu.dataset.cpdJupyterhubUser = hubUser;
    menu.dataset.cpdJupyterhubDisconnectHref = disconnectHref;
    menu.replaceChildren(...items);
  }}

  function updateConnectLinks() {{
    for (const link of document.querySelectorAll("a")) {{
      const isConnectLink = link.dataset.cpdJupyterhubConnect === "1"
        || link.href.includes("/services/uksa-thebe/bootstrap")
        || link.textContent.trim() === "Connect JupyterHub"
        || link.textContent.trim() === "Connect to JupyterHub"
        || link.textContent.trim() === "Connected to JupyterHub"
        || link.textContent.trim() === "JupyterHub";
      if (!isConnectLink) continue;
      link.dataset.cpdJupyterhubConnect = "1";
      link.removeAttribute("target");
      link.removeAttribute("rel");
      link.classList.add("cpd-jupyterhub-connect");
      const {{ wrapper, menu }} = ensureConnectMenu(link);
      const state = connectState();
      const labelText = connectLabel(state);
      const href = hubConnected ? hubHomePath : bootstrapUrl();
      if (link.getAttribute("href") !== href) link.setAttribute("href", href);
      if (
        link.dataset.cpdJupyterhubState !== state
        || !link.querySelector(".cpd-jupyterhub-status")
        || !link.querySelector(".cpd-jupyterhub-caret")
        || link.querySelector(".cpd-jupyterhub-label")?.textContent !== labelText
      ) {{
        link.dataset.cpdJupyterhubState = state;
        const marker = document.createElement("span");
        marker.className = "cpd-jupyterhub-status";
        marker.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.className = "cpd-jupyterhub-label";
        label.textContent = labelText;
        const caret = document.createElement("span");
        caret.className = "cpd-jupyterhub-caret";
        caret.setAttribute("aria-hidden", "true");
        link.replaceChildren(marker, label, caret);
      }}
      link.setAttribute(
        "aria-label",
        state === "connected"
          ? "Connected to CPD JupyterHub. Open options."
          : labelText
      );
      link.title = state === "connected"
        ? "Open CPD JupyterHub options"
        : "Authenticate with CPD JupyterHub for in-page code execution";
      if (state === "connecting") {{
        link.setAttribute("aria-busy", "true");
      }} else {{
        link.removeAttribute("aria-busy");
      }}
      if (hubConnected) {{
        updateConnectMenu(menu);
        link.setAttribute("aria-controls", menu.id || "");
        link.setAttribute("aria-expanded", wrapper.dataset.cpdJupyterhubMenuOpen === "1" ? "true" : "false");
        link.setAttribute("aria-haspopup", "menu");
      }} else {{
        setConnectMenuOpen(wrapper, false);
        link.removeAttribute("aria-controls");
        link.removeAttribute("aria-expanded");
        link.removeAttribute("aria-haspopup");
      }}
      if (link.dataset.cpdJupyterhubClickGuard !== "1") {{
        link.dataset.cpdJupyterhubClickGuard = "1";
        link.addEventListener("click", (event) => {{
          event.preventDefault();
          event.stopImmediatePropagation();
          const currentWrapper = link.closest(".cpd-jupyterhub-menu-wrap");
          if (hubConnected && currentWrapper) {{
            const open = currentWrapper.dataset.cpdJupyterhubMenuOpen !== "1";
            closeConnectMenus(open ? currentWrapper : null);
            setConnectMenuOpen(currentWrapper, open);
            return;
          }}
          if (window.__cpdJupyterhubConnecting) return;
          window.__cpdJupyterhubConnecting = true;
          hubConnecting = true;
          link.setAttribute("aria-busy", "true");
          updateConnectLinks();
          window.location.assign(link.getAttribute("href") || bootstrapUrl());
        }}, true);
      }}
    }}
  }}

  document.addEventListener("click", (event) => {{
    const target = event.target instanceof Node ? event.target : null;
    for (const wrapper of document.querySelectorAll(".cpd-jupyterhub-menu-wrap[data-cpd-jupyterhub-menu-open='1']")) {{
      if (target && wrapper.contains(target)) continue;
      setConnectMenuOpen(wrapper, false);
    }}
  }}, true);

  document.addEventListener("keydown", (event) => {{
    if (event.key !== "Escape") return;
    closeConnectMenus();
  }});

  async function updateConnectionStatus() {{
    try {{
      const response = await fetch(thebeStatusPath, {{
        credentials: "include",
        headers: {{ accept: "application/json" }},
      }});
      if (!response.ok) return;
      const status = await response.json();
      hubConnected = status.connected === true;
      hubConnecting = false;
      hubUser = typeof status.user === "string"
        ? status.user
        : (status.user && typeof status.user.name === "string" ? status.user.name : "");
      updateConnectLinks();
    }} catch (_error) {{
      // Leave the connect action in its default state when status is unavailable.
    }}
  }}

  function updateLaunchLinks() {{
    const href = currentNotebookUrl() || defaultUrl;
    for (const link of document.querySelectorAll("a")) {{
      if (link.textContent.trim() !== "Open in JupyterHub") continue;
      if (!link.href.includes("/hub/user-redirect/git-pull")) continue;
      if (link.getAttribute("href") !== href) link.setAttribute("href", href);
      link.title = notebookUrls[currentSlug()]
        ? "Open this notebook in CPD JupyterHub"
        : "Open the course in CPD JupyterHub";
    }}
    updateConnectLinks();
    updateThebeLaunchButtons();
  }}

  function updateThebeLaunchButtons() {{
    for (const button of document.querySelectorAll("button")) {{
      const label = [
        button.getAttribute("aria-label"),
        button.getAttribute("title"),
        button.textContent,
      ].join(" ").toLowerCase();
      if (!label.includes("start compute environment") && !label.includes("launch kernel")) continue;
      if (button.dataset.cpdJupyterhubBootstrap === "1") continue;
      button.dataset.cpdJupyterhubBootstrap = "1";
      button.addEventListener("click", (event) => {{
        const params = new URLSearchParams(window.location.search);
        if (params.get(thebeReadyParam) === "1") return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.href = bootstrapUrl(
          currentReturnPath({{ startThebe: true }}),
          {{ startThebe: true }}
        );
      }}, true);
    }}
  }}

  updateThebeLaunchButtons();

  let pending = false;
  let started = false;
  let observer = null;
  function scheduleUpdate() {{
    if (!started) return;
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {{
      pending = false;
      updateLaunchLinks();
    }});
  }}

  for (const method of ["pushState", "replaceState"]) {{
    const original = history[method];
    history[method] = function (...args) {{
      const result = original.apply(this, args);
      scheduleUpdate();
      return result;
    }};
  }}

  window.addEventListener("popstate", scheduleUpdate);

  function startUpdates() {{
    if (started) return;
    started = true;
    observer = new MutationObserver(scheduleUpdate);
    observer.observe(document.documentElement, {{
      childList: true,
      subtree: true,
    }});
    updateLaunchLinks();
    updateConnectionStatus();
  }}

  function startAfterHydration() {{
    const idle = window.requestIdleCallback || ((callback) => setTimeout(callback, 0));
    idle(() => setTimeout(startUpdates, 750));
  }}

  if (document.readyState === "complete") {{
    startAfterHydration();
  }} else {{
    window.addEventListener("load", startAfterHydration, {{ once: true }});
  }}
}})();
</script>
{MARKER_END}"""


def inject(build_dir: Path, html_path: Path, script: str) -> bool:
    original = html_path.read_text(encoding="utf-8")
    html = re.sub(
        rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n?",
        "",
        original,
        flags=re.DOTALL,
    )
    html = rewrite_static_connect_urls(html, page_path(build_dir, html_path))
    if "</body>" not in html:
        raise ValueError(f"{html_path} does not contain </body>")
    updated = html.replace("</body>", f"{script}\n</body>", 1)
    changed = updated != original
    if changed:
        html_path.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=BUILD_DIR)
    args = parser.parse_args()

    entrypoint = args.build_dir / HTML_ENTRYPOINT
    project = extract_project(entrypoint.read_text(encoding="utf-8"))
    routes = notebook_routes(project)
    script = injected_script(routes)

    changed = 0
    for html_path in args.build_dir.rglob("*.html"):
        changed += int(inject(args.build_dir, html_path, script))
    print(f"Injected {len(routes)} CPD notebook launch routes into {changed} HTML file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
