import json
import os
import pathlib
import requests
import redis
import argparse
import time
from config import token

# --- CONFIG ---
ORG = "MISP"
PER_PAGE = 500

with open(os.path.join(pathlib.Path(__file__).parent, "skip_repo.json"), "r") as read_file:
    SKIP_REPOS = json.load(read_file)

# --- REDIS ---
redcon = redis.StrictRedis(host='localhost', port=6379, db=11, decode_responses=True)

headers = {
    "Authorization": f"Bearer {token}"
}


# -----------------------------
# Helper: pagination
# -----------------------------
def get_all_pages(url):
    results = []

    while url:
        r = requests.get(url, headers=headers)
        if r.status_code == 202:
            # stats not ready
            print("Stats not ready, waiting...")
            time.sleep(2)
            continue

        r.raise_for_status()
        results.extend(r.json())

        url = None
        if "link" in r.headers:
            for link in r.headers["link"].split(","):
                if 'rel="next"' in link:
                    url = link[link.find("<")+1:link.find(">")]
                    break

    return results


# -----------------------------
# Get all repos
# -----------------------------
def get_repos():
    url = f"https://api.github.com/orgs/{ORG}/repos?per_page={PER_PAGE}"
    return get_all_pages(url)

# -----------------------------
# Pending management
# -----------------------------
def mark_pending(repo_name):
    now = int(time.time())
    redcon.sadd("repos:pending", repo_name)
    redcon.hset("repos:pending:ts", repo_name, now)

def clear_pending(repo_name):
    redcon.srem("repos:pending", repo_name)
    redcon.hdel("repos:pending:ts", repo_name)

# -----------------------------
# Trigger stats (like github3)
# -----------------------------
def trigger():
    print("Triggering stats computation for all repos...")
    repos = get_repos()

    for repo in repos:
        name = repo["name"]

        if name in SKIP_REPOS:
            print(f"Skip repo {name}")
            continue

        print(f"Trigger stats for {name}")

        url = f"https://api.github.com/repos/{ORG}/{name}/stats/contributors"

        try:
            r = requests.get(url, headers=headers)

            # GitHub may return 202 while computing
            if r.status_code == 202:
                print(f"Stats computing for {name}")
            elif r.status_code == 200:
                print(f"Stats ready for {name}")
        except Exception as e:
            print(f"Error on {name}: {e}")


# -----------------------------
# Collect stats
# -----------------------------
def collect(retry_pending=False):
    print("Collecting stats...")

    if retry_pending:
        repos_names = list(redcon.smembers("repos:pending"))
        print(f"Retrying {len(repos_names)} pending repos...")
        repos = [{"name": name} for name in repos_names]
    else:
        repos = get_repos()

    cp = 0
    total_repos = len(repos)

    for repo in repos:
        cp += 1
        name = repo["name"]

        if name in SKIP_REPOS:
            print(f"Skip repo {name} ({cp}/{total_repos})")
            continue

        print(f"[+] Processing {name} ({cp}/{total_repos})")

        redcon.sadd("repositories", name)

        url = f"https://api.github.com/repos/{ORG}/{name}/stats/contributors"

        stats = None
        success = False

        for attempt in range(6):
            r = requests.get(url, headers=headers)

            if r.status_code == 202:
                print(f"\tWaiting stats for {name} (attempt {attempt+1})...")
                time.sleep(7)
                continue

            try:
                r.raise_for_status()
                stats = r.json()
                success = True
            except Exception as e:
                print(f"\t[-] Error parsing stats for {name}: {e}")
                stats = None

            break

        # ---- failure case
        if not success or not stats:
            print(f"\t[-] Failed to collect stats for {name}, adding to pending\n")
            mark_pending(name)
            continue

        # ---- success case
        print(f"\t[✓] Stats collected for {name}")
        clear_pending(name)

        seen = set()

        for cstat in stats:
            author = cstat.get("author")
            if not author:
                continue

            login = author.get("login")
            total = cstat.get("total", 0)

            if not login:
                continue

            # skip bots
            if login.endswith("[bot]"):
                continue

            redcon.zincrby(f"r:{name}", total, login)
            redcon.zincrby("topcommit", total, login)

            redcon.sadd("users", login)
            redcon.set(f"a:{login}", author.get("avatar_url", ""))

            # ensure 1 per repo
            if login not in seen:
                redcon.zincrby("topversatile", 1, login)
                seen.add(login)

# -----------------------------
# List pending repos
# -----------------------------
def list_pending():
    pending = sorted(redcon.smembers("repos:pending"))

    if not pending:
        print("No pending repositories 🎉")
        return

    now = int(time.time())

    print(f"Pending repositories ({len(pending)}):\n")

    for i, repo in enumerate(pending, 1):
        ts = redcon.hget("repos:pending:ts", repo)

        if ts:
            ts = int(ts)
            age = now - ts
            hours = age // 3600
            minutes = (age % 3600) // 60
            ts_str = f"{hours}h {minutes}m ago"
        else:
            ts_str = "unknown"

        print(f"{i:3d}. {repo}  (last failure: {ts_str})")

# -----------------------------
# CLI
# -----------------------------
parser = argparse.ArgumentParser(description="Generate contributors stats from GitHub API")
parser.add_argument("--all", action="store_true", help="Run stats triggering and collection in one shot (default).")
parser.add_argument("--trigger", action="store_true", help="Trigger stats only.")
parser.add_argument("--collect", action="store_true", help="Collect stats only.")
parser.add_argument(
    "--retry-pending",
    action="store_true",
    help="Retry only repos that previously failed"
)
parser.add_argument(
    "--list-pending",
    action="store_true",
    help="List repositories that failed and are pending retry"
)


args = parser.parse_args()


if args.list_pending:
    list_pending()
elif args.retry_pending:
    collect(retry_pending=True)
elif args.trigger:
    trigger()
elif args.collect:
    redcon.flushdb()
    collect()
else:
    redcon.flushdb()
    trigger()
    collect()
