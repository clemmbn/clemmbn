"""
stats.py — fetches the live numbers printed on the receipt from GitHub's
GraphQL API.

Main responsibilities
    - Resolve a token: GH_STATS_TOKEN (GitHub Action secret) or GITHUB_TOKEN,
      falling back to the local `gh auth token`.
    - Walk every repository the token can see and compute:
        started   owned, non-fork repos (public + private, archived included:
                  an abandoned project still counts as one started)
        commits   commits authored by the viewer on each repo's default branch
        language  top language by bytes across owned, non-fork repos
        last      most recently pushed owned repo (name hidden if private)

Non-obvious constraints
    - Commits are counted per repo via `history(author:)` instead of the
      contribution graph (`contributionsCollection`): the graph only covers a
      one-year window per query and silently skips commits it doesn't credit,
      which undercounted ~740 real commits as ~300.
    - Only default branches are counted; work living only on feature
      branches is not (would cost one query per branch).
    - The profile repo itself is excluded from "last pushed", otherwise the
      Action's own reprint commit would always make it the latest.
    - Private repo *names* never leave this module; only counts, languages and
      dates are used for them.
"""

import json
import os
import subprocess
import urllib.request
from collections import Counter
from datetime import datetime

API = "https://api.github.com/graphql"
PROFILE_REPO = "clemmbn/clemmbn"
# Notebook output (base64 images, JSON) inflates byte counts without being
# code anyone "writes in"; markup languages aren't what a reader cares about.
IGNORED_LANGUAGES = {"Jupyter Notebook", "HTML", "CSS", "SCSS"}

REPOS_QUERY = """
query($id: ID!, $cursor: String) {
  viewer {
    repositories(ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER],
                 first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner isFork isPrivate pushedAt
        owner { login }
        languages(first: 10) { edges { size node { name } } }
        defaultBranchRef { target { ... on Commit { history(author: {id: $id}) { totalCount } } } }
      }
    }
  }
}
"""


def token():
    """Return a GitHub token from the environment or the local gh CLI.

    Raises RuntimeError when none is available, so a misconfigured Action
    fails loudly instead of printing a receipt full of zeros.
    """
    for var in ("GH_STATS_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            print(f"[stats] using token from ${var}")
            return os.environ[var]
    try:
        tok = subprocess.run(["gh", "auth", "token"], check=True,
                             capture_output=True, text=True).stdout.strip()
        print("[stats] using token from `gh auth token`")
        return tok
    except (OSError, subprocess.CalledProcessError) as err:
        raise RuntimeError("No GitHub token: set GH_STATS_TOKEN or run `gh auth login`") from err


def graphql(tok, query, variables=None):
    """POST one GraphQL query; return its `data` dict.

    tok (str): bearer token. query (str): GraphQL document.
    variables (dict|None): query variables.
    Raises RuntimeError on GraphQL-level errors (HTTP errors raise urllib's).
    """
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"bearer {tok}", "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def all_repos(tok):
    """Return (viewer login, every repo node the token can see), paginated."""
    viewer = graphql(tok, "{ viewer { id login } }")["viewer"]
    repos, cursor = [], None
    while True:
        page = graphql(tok, REPOS_QUERY, {"id": viewer["id"], "cursor": cursor})
        conn = page["viewer"]["repositories"]
        repos += conn["nodes"]
        print(f"[stats] fetched {len(repos)} repos so far")
        if not conn["pageInfo"]["hasNextPage"]:
            return viewer["login"], repos
        cursor = conn["pageInfo"]["endCursor"]


def commit_count(repo):
    """Return the viewer's commits on a repo's default branch (0 if empty)."""
    ref = repo["defaultBranchRef"]
    return ref["target"]["history"]["totalCount"] if ref else 0


def top_language(repos):
    """Return the language with the most bytes across `repos`, or None."""
    sizes = Counter()
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            if edge["node"]["name"] not in IGNORED_LANGUAGES:
                sizes[edge["node"]["name"]] += edge["size"]
    print(f"[stats] languages by bytes: {sizes.most_common(4)}")
    return sizes.most_common(1)[0][0] if sizes else None


def fetch():
    """Fetch and compute every receipt stat.

    Returns (dict): started (int), commits (int), language (str|None),
    last_name (str, "[REDACTED]" if private), last_date (datetime).
    """
    login, repos = all_repos(token())
    owned = [r for r in repos if r["owner"]["login"] == login and not r["isFork"]]
    # Latest real activity: skip the profile repo (the bot pushes there)
    latest = max((r for r in owned if r["nameWithOwner"] != PROFILE_REPO),
                 key=lambda r: r["pushedAt"])
    stats = {
        "started": len(owned),
        "commits": sum(commit_count(r) for r in repos),
        "language": top_language(owned),
        "last_name": "[REDACTED]" if latest["isPrivate"] else latest["nameWithOwner"].split("/")[1],
        "last_date": datetime.fromisoformat(latest["pushedAt"].replace("Z", "+00:00")),
    }
    print(f"[stats] {len(repos)} visible repos, {len(owned)} owned non-fork -> "
          f"{ {k: v for k, v in stats.items()} }")
    return stats


if __name__ == "__main__":
    fetch()
