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
    thebe_ready_param = json.dumps(THEBE_READY_PARAM)
    return f"""{MARKER_START}
<script id="cpd-jupyterhub-launch-links">
(() => {{
  const rootPath = {root_path};
  const defaultUrl = {default_url};
  const thebeBootstrapPath = {thebe_bootstrap_path};
  const thebeReadyParam = {thebe_ready_param};
  const notebookUrls = {routes_json};

  function currentReturnPath(options = {{}}) {{
    const url = new URL(window.location.href);
    if (options.startThebe) url.searchParams.set("thebe", "1");
    if (options.startThebe) url.searchParams.set(thebeReadyParam, "1");
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

  function updateConnectLinks() {{
    const href = bootstrapUrl();
    for (const link of document.querySelectorAll("a")) {{
      if (link.textContent.trim() !== "Connect JupyterHub") continue;
      if (!link.href.includes("/services/uksa-thebe/bootstrap")) continue;
      if (link.getAttribute("href") !== href) link.setAttribute("href", href);
      link.removeAttribute("target");
      link.removeAttribute("rel");
      link.title = "Authenticate with CPD JupyterHub for in-page code execution";
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
