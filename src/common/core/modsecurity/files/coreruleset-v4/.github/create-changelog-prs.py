#! /usr/bin/env python

import argparse
import subprocess
import json
import datetime
import sys
import os
import re
from inspect import getframeinfo, currentframe

DEVELOPERS = {}
CHANGELOG_LABEL = "changelog-pr"


def get_pr(repository: str, number: int) -> dict:
    command = f"""gh pr view \
        --repo "{repository}" \
        "{number}" \
        --json mergeCommit,mergedBy,title,author,headRefName,baseRefName,number,body
    """
    with subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as proc:
        pr_json, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        return json.loads(pr_json)


def get_prs(
    repository: str, start_date: datetime.date, end_date: datetime.date, dry_run: bool
) -> (list, list):
    print(f"Fetching merged PRs from {start_date} through {end_date}")
    options = ['--merged-at "{start_date}..{end_date}"']
    all_prs = fetch_prs(repository, options, dry_run)

    print(f"Fetching open changelog PRs from {start_date} through {end_date}")
    options = ["--state open"]
    all_prs.extend(fetch_prs(repository, options, dry_run))
    prs = []
    changelog_prs = []
    for result in all_prs:
        if CHANGELOG_LABEL in [label["name"] for label in result["labels"]]:
            changelog_prs.append(get_pr(repository, result["number"]))
        else:
            prs.append(get_pr(repository, result["number"]))

    return (prs, changelog_prs)


def fetch_prs(repository: str, options: list[str], dry_run: bool) -> list[dict]:
    command = f"""gh search prs \
        --repo "{repository}" \
        --json number,labels \
    """
    for option in options:
        command += " " + option

    if dry_run:
        print(command)
        return []

    with subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as proc:
        prs_json, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        return json.loads(prs_json)


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


def create_prs(
    repository: str,
    merged_by_prs_map: dict,
    changelog_prs: list,
    start_date: datetime.date,
    end_date: datetime.date,
    dry_run: bool,
):
    for author in merged_by_prs_map.keys():
        create_pr(
            repository,
            author,
            merged_by_prs_map[author],
            changelog_prs,
            start_date,
            end_date,
            dry_run,
        )


def create_pr(
    repository: str,
    merged_by: str,
    prs: list,
    changelog_prs: list,
    start_date: datetime.date,
    end_date: datetime.date,
    dry_run: bool,
):
    if len(prs) == 0:
        return

    print(f"Creating changelog PR for @{merged_by}")

    base_branch = prs[0]["baseRefName"]
    checkout_base(base_branch, dry_run)
    pr_branch_name = create_pr_branch(start_date, end_date, merged_by, dry_run)
    pr_body, changelog_lines = generate_content(prs, merged_by)
    create_commit(changelog_lines, dry_run)
    push_pr_branch(pr_branch_name, dry_run)

    print("\tCreating PR...")
    command = f"""gh pr create \
        --repo "{repository}" \
        --assignee "{merged_by}" \
        --base "{base_branch}" \
        --label "{CHANGELOG_LABEL}" \
        --title "chore: changelog updates since {start_date}, merged by @{merged_by}" \
        --body-file -
    """

    if dry_run:
        print(command)
        return

    with subprocess.Popen(
        command,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:
        outs, errors = proc.communicate(input=pr_body.encode())
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)
        print(f"Created PR: {outs.decode()}")


def checkout_base(base_ref: str, dry_run: bool):
    print("\tChecking out base ref ...")
    command = f"git checkout {base_ref}"

    if dry_run:
        print(command)
        return

    with subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:
        outs, errors = proc.communicate()
        if proc.returncode != 0:
            print_errors(errors)
            sys.exit(1)


def create_commit(changelog_lines: str, dry_run: bool):
    print("\tCreating commit...")

    if dry_run:
        print("Changelogs to append:")
        print(changelog_lines)
    else:
        with open(".changes-pending.md", "a", encoding="utf-8") as changelog:
            changelog.write(changelog_lines)

    command = "git commit .changes-pending.md -m 'Add pending changelog entries'"
    if dry_run:
        print(command)
    else:
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
    regex = re.compile(r"^\s*?-\s*?\[([^]]+)\]\s*?\(http.*/([^/]+)\s*?\)")
    with open("CONTRIBUTORS.md", "rt", encoding="utf-8") as handle:
        line = handle.readline()
        while not ("##" in line and "Contributors" in line):
            match = regex.match(line)
            if match:
                DEVELOPERS[match.group(2)] = match.group(1)
            line = handle.readline()


def create_pr_branch(
    start_date: datetime.date,
    end_date: datetime.date,
    author: str,
    dry_run: bool,
) -> str:
    print("\tCreating branch...")
    branch_name = f"changelog-updates-{start_date}-{end_date}-{author}"
    command = f"git checkout -b {branch_name}"

    if dry_run:
        print(command)
    else:
        with subprocess.Popen(command, shell=True, stderr=subprocess.PIPE) as proc:
            _, errors = proc.communicate()
            if proc.returncode != 0:
                print_errors(errors)
                sys.exit(1)

    return branch_name


def push_pr_branch(branch_name: str, dry_run: bool):
    print("\tPushing branch...")
    command = f"git push -u origin {branch_name}"

    if dry_run:
        print(command)
    else:
        with subprocess.Popen(command, shell=True, stderr=subprocess.PIPE) as proc:
            _, errors = proc.communicate()
            if proc.returncode != 0:
                print_errors(errors)
                sys.exit(1)


def run():
    # disable pager
    os.environ["GH_PAGER"] = ""
    # set variables for Git
    os.environ["GIT_AUTHOR_NAME"] = "changelog-pr-bot"
    os.environ["GIT_AUTHOR_EMAIL"] = "dummy@coreruleset.org"
    os.environ["GIT_COMMITTER_NAME"] = "changelog-pr-bot"
    os.environ["GIT_COMMITTER_EMAIL"] = "dummy@coreruleset.org"

    args = parse_command_line()
    from_date = (
        args.from_date
        if args.from_date is not None
        else args.to_date - datetime.timedelta(days=7)
    )
    run_workflow(args.source, args.target, from_date, args.to_date, args.dry_run)


def run_workflow(
    source_repository: str,
    target_repository: str,
    start_date: datetime.date,
    end_date: datetime.date,
    dry_run: bool,
):
    prs, changelog_prs = get_prs(source_repository, start_date, end_date, dry_run)
    prs_length = len(prs)
    print(f"Found {prs_length} PRs")
    if prs_length == 0:
        return

    prs = filter_prs(prs, changelog_prs)

    merged_by_prs_map = parse_prs(prs)
    create_prs(
        target_repository,
        merged_by_prs_map,
        changelog_prs,
        start_date,
        end_date,
        dry_run,
    )


def filter_prs(prs: list, changelog_prs: list) -> list:
    filtered_prs = []
    for pr in prs:
        found = False
        for cpr in changelog_prs:
            for line in cpr["body"].splitlines():
                if line.endswith(f"[#{pr['number']}]"):
                    print(
                        f"PR {pr['number']} was processed in a previous run. Skipping..."
                    )
                    found = True
                    break
            if found:
                break
        if not found:
            filtered_prs.append(pr)
    return filtered_prs


def print_errors(errors: str):
    print(f"{getframeinfo(currentframe().f_back).lineno}:", errors)


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="coreruleset/coreruleset")
    parser.add_argument("--target", default="coreruleset/coreruleset")
    # the cron schedule for the workflow uses UTC
    parser.add_argument("--from", type=datetime.date.fromisoformat, dest="from_date")
    parser.add_argument(
        "--to",
        type=datetime.date.fromisoformat,
        default=datetime.datetime.now(datetime.timezone.utc).date(),
        dest="to_date",
    )
    parser.add_argument("--dry-run", action="store_true")

    return parser.parse_args()


if __name__ == "__main__":
    run()
