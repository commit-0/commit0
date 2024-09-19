import datasets
import subprocess

import requests
from bs4 import BeautifulSoup

def get_github_avatar(repo):
    """
    Given a GitHub repo in the format 'owner/repo', get the avatar URL of the organization or user.
    """
    try:
        org = repo.split("/")[0]
        # Construct the URL for the repo
        url = f"https://github.com/{org}"

        # Make a request to the page
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code != 200:
            print(f"Failed to fetch page for {repo}. Status code: {response.status_code}")
            return None

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the meta tag with property "og:image" which contains the avatar URL
        meta_tag = soup.find('meta', property='og:image')

        if meta_tag and 'content' in meta_tag.attrs:
            avatar_url = meta_tag['content']
            return avatar_url
        else:
            print(f"Avatar URL not found for {repo}")
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

d = datasets.load_dataset("wentingzhao/commit0_docstring", split="test")

print(d)



print("|  | Name |  Repo | Commit0 | Tests |  | ")
print("|--|--------|-------|----|----|------| ")
overload = {
    "simpy" : "https://simpy.readthedocs.io/en/4.1.1/_images/simpy-logo-small.png",
    "tinydb" : "https://raw.githubusercontent.com/msiemens/tinydb/master/artwork/logo.png",
    "bitstring": "https://bitstring.readthedocs.io/en/stable/_images/bitstring_logo.png",
    "seaborn":     "https://raw.githubusercontent.com/mwaskom/seaborn/master/doc/_static/logo-wide-lightbg.svg",
    "statsmodels": "https://raw.githubusercontent.com/statsmodels/statsmodels/main/docs/source/images/statsmodels-logo-v2-horizontal.svg",
    "pyboy" : "https://github.com/Baekalfen/PyBoy/raw/master/extras/README/pyboy.svg",
}
skip = {
    "pyjwt",
    "wcwidth",
    "chardet",
    "dnspython",
    "imapclient",
    "pexpect",
    "dulwich",
    "voluptuous",
    "requests",
    "tlslite-ng",
    "more-itertools",
    "deprecated",
    "cachetools",
    "paramiko",
    "jedi",
    "sqlparse",
}
for i, ex in enumerate(d):
    img = get_github_avatar(ex["original_repo"])

    name = ex["repo"].split("/")[1]
    result = subprocess.check_output(f"commit0 get-tests {name} | wc", shell=True, text=True)

    tests = int(result.split()[0])
    if name.lower() not in skip and name.lower() not in overload:
        img = f"<img src='{img}' width='100px'/>"
    elif name.lower() in overload:
        img = f"<img src='{overload[name.lower()]}' width='100px'/>"
    else:
        img = f"<b>{name}</b>"
    print(f"| {img} | [{name}]({ex['setup']['specification']}) | [[orig](http://github.com/{ex['original_repo']})] | [[commit0](http://github.com/{ex['repo']})] | {tests} | <img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAABkCAQAAADtJZLrAAAAD0lEQVR42mNkYGAcRcQhADxaAGWhD8eHAAAAAElFTkSuQmCC'/> |")
