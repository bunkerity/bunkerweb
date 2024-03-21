#! /usr/bin/env python

import subprocess
import json
import datetime
import sys
import os
import re
from inspect import getframeinfo, currentframe

DEVELOPERS = {}

def get_pr(repository: str, number: int) -> dict:
    command = f"""gh pr view \
        --repo "{repository}" \
        "{number}" \
        --json mergeCommit,mergedBy,title,author,headRefName,baseRefName,number
    """
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        pr_json, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        return json.loads(pr_json)

def get_prs(repository: str, start_date: datetime.date, end_date: datetime.date) -> list:
    print("Fetching PR for start_date")
    command = f"""gh search prs \
        --repo "{repository}" \
        --merged-at "{end_date}..{start_date}" \
        --json number \
        -- \
        -label:changelog-pr # ignore changelog prs
    """
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        prs_json, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        prs = []
        for result in json.loads(prs_json):
            prs.append(get_pr(repository, result["number"]))

        return prs

def parse_prs(prs: list) -> dict:
    pr_map = {}
    for pr in prs:
        merged_by = pr["mergedBy"]["login"]
        if merged_by not in pr_map:
            pr_list = []
            pr_map[merged_by] = pr_list
        else:
            pr_list = pr_map[merged_by]
        pr_list.append(pr)
    return pr_map


# Accepts a single date on purpose. Gathering PRs over more than a single day
# is for debugging only.
def create_prs(repository: str, merged_by_prs_map: dict, day: datetime.date):
    base_pr = find_latest_open_changelog_pr(repository)
    base_ref = base_pr["headRefName"] if base_pr else None
    for author in merged_by_prs_map.keys():
        base_ref = create_pr(repository, base_ref, author, merged_by_prs_map[author], day)

def find_latest_open_changelog_pr(repository: str) -> dict | None:
    command = f"""gh search prs \
        --repo "{repository}" \
        --label "changelog-pr" \
        --state open \
        --sort created \
        --json number
    """
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        pr_json, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        ids = json.loads(pr_json)
        base_pr_id = ids[0]["number"] if ids else None
        if not base_pr_id:
            print("No open changelog PR found to use as base")
            return None

    base_pr = get_pr(repository, base_pr_id)
    print(f"Found existing changelog PR to use as base: {base_pr_id}")
    return base_pr

def create_pr(repository: str, base_ref: str | None, merged_by: str, prs: list, day: datetime.date) -> str:
    if len(prs) == 0:
        return base_ref

    print(f"Creating changelog PR for @{merged_by}")

    base_branch = base_ref if base_ref else prs[0]["baseRefName"]
    pr_branch_name = create_pr_branch(day, merged_by, base_branch)
    pr_body, changelog_lines = generate_content(prs, merged_by)
    create_commit(changelog_lines)
    push_pr_branch(pr_branch_name)

    print("\tCreating PR...")
    command = f"""gh pr create \
        --repo "{repository}" \
        --assignee "{merged_by}" \
        --base "{base_branch}" \
        --label "changelog-pr" \
        --title "chore: changelog updates for {day}, merged by @{merged_by}" \
        --body-file -
    """

    with subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        outs, errors = proc.communicate(input=pr_body.encode())
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        print(f"Created PR: {outs.decode()}")
        return pr_branch_name

def create_commit(changelog_lines: str):
    print("\tCreating commit...")
    with open('.changes-pending.md', 'a', encoding='utf-8s') as changelog:
        changelog.write(changelog_lines)

    command = "git commit .changes-pending.md -m 'Add pending changelog entries'"
    with subprocess.Popen(command, shell=True, stderr=subprocess.PIPE) as proc:
        _, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)

def generate_content(prs: list, merged_by: str) -> (str, str):
    print("\tGenerating PR content...")
    changelog_lines = ""
    pr_body = f"This PR was auto-generated to update the changelog with the following entries, merged by @{merged_by}:\n```\n"
    pr_links = ""
    for pr in prs:
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_author = get_pr_author_name(pr["author"]["login"])
        new_line = f" * {pr_title} ({pr_author}) [#{pr_number}]\n"
        pr_body += new_line
        pr_links += f"- #{pr_number}\n"

        changelog_lines += new_line
    pr_body += "```\n\n" + pr_links

    return pr_body, changelog_lines

def get_pr_author_name(login: str) -> str:
    if len(DEVELOPERS) == 0:
        parse_contributors()

    return DEVELOPERS[login] if login in DEVELOPERS else f"@{login}"

def parse_contributors():
    regex = re.compile(r'^\s*?-\s*?\[([^]]+)\]\s*?\(http.*/([^/]+)\s*?\)')
    with open('CONTRIBUTORS.md', 'rt', encoding='utf-8') as handle:
        line = handle.readline()
        while not ('##' in line and 'Contributors' in line):
            match = regex.match(line)
            if match:
                DEVELOPERS[match.group(2)] = match.group(1)
            line = handle.readline()

def create_pr_branch(day: datetime.date, author: str, base_branch: str) -> str:
    print("\tCreating branch...")
    branch_name = f"changelog-updates-for-{day}-{author}"
    command = f"git checkout {base_branch}; git checkout -b {branch_name}"
    with subprocess.Popen(command, shell=True, stderr=subprocess.PIPE) as proc:
        _, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)

        return branch_name

def push_pr_branch(branch_name: str):
    print("\tPushing branch...")
    command = f"git push -u origin {branch_name}"
    with subprocess.Popen(command, shell=True, stderr=subprocess.PIPE) as proc:
        _, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)

def run():
    # disable pager
    os.environ["GH_PAGER"] = ''
    # set variables for Git
    os.environ["GIT_AUTHOR_NAME"] = "changelog-pr-bot"
    os.environ["GIT_AUTHOR_EMAIL"] = "dummy@coreruleset.org"
    os.environ["GIT_COMMITTER_NAME"] = "changelog-pr-bot"
    os.environ["GIT_COMMITTER_EMAIL"] = "dummy@coreruleset.org"

    source_repository = 'coreruleset/coreruleset'
    target_repository = source_repository
    # the cron schedule for the workflow uses UTC
    start_date = datetime.datetime.now(datetime.timezone.utc).date()
    days = 1

    if len(sys.argv) > 1 and len(sys.argv[1]) > 0:
        source_repository = sys.argv[1]
    if len(sys.argv) > 2 and len(sys.argv[2]) > 0:
        target_repository = sys.argv[2]
    if len(sys.argv) > 3 and len(sys.argv[3]) > 0:
        start_date = datetime.date.fromisoformat(sys.argv[3])
    if len(sys.argv) > 4 and len(sys.argv[4]) > 0:
        days = int(sys.argv[4])

    run_workflow(source_repository, target_repository, start_date, days)

def run_workflow(source_repository: str, target_repository: str, start_date: datetime.date, days: int):
    end_date = start_date - datetime.timedelta(days=days)
    prs = get_prs(source_repository, start_date, end_date)
    prs_length = len(prs)
    print(f"Found {prs_length} PRs")
    if prs_length == 0:
        return

    merged_by_prs_map = parse_prs(prs)
    create_prs(target_repository, merged_by_prs_map, start_date)

def print_errors(errors: str):
    print(f"{getframeinfo(currentframe().f_back).lineno}:", errors)

if __name__ == "__main__":
    run()
