"""Check the built landing page's student-facing JupyterLab launch link."""
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append(("".join(self.label).strip(), self.href))
            self.href = None


page = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_build/html/index.html")
links = Links()
links.feed(page.read_text())
targets = [urlsplit(href) for label, href in links.links
           if label == "Open CPD Training in JupyterLab"]
assert len(targets) == 1, "Expected one clearly labelled training workspace link"
target = targets[0]
assert target.path == "/jupyterhub/hub/user-redirect/git-pull", (
    "The Lab link must use the notebook-launch route, not the book-connect route"
)
query = parse_qs(target.query)
assert query["repo"] == ["https://github.com/xangma/UKSA_SoftwareDataAI_Training"]
assert query["branch"] == ["main"]
assert query["urlpath"] == ["lab/tree/UKSA_SoftwareDataAI_Training?autodecode"]
print("Built CPD Training landing-page JupyterLab link passed")
