#! /usr/bin/env python

import subprocess
import json
import datetime
import sys
import os
import re

DEVELOPERS = dict()

def get_pr(repository: str, number: int) -> dict:
	command = f"""gh pr view \
		--repo "{repository}" \
		"{number}" \
		--json mergeCommit,mergedBy,title,author,baseRefName,number
	"""
	proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	pr_json, errors = proc.communicate()
	if proc.returncode != 0:
		print(errors)
		exit(1)
	return json.loads(pr_json)

def get_prs(repository: str, day: datetime.date) -> list:
	print(f"Fetching PRs for {day}")
	command = f"""gh search prs \
		--repo "{repository}" \
		--merged-at "{day}" \
		--json number \
		-- \
		-label:changelog-pr # ignore changelog prs
	"""
	proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	prs_json, errors = proc.communicate()
	if proc.returncode != 0:
		print(errors)
		exit(1)
	prs = list()
	for result in json.loads(prs_json):
		prs.append(get_pr(repository, result["number"]))

	return prs

def parse_prs(prs: list) -> dict:
	pr_map = dict()
	for pr in prs:
		merged_by = pr["mergedBy"]["login"]
		if merged_by not in pr_map:
			pr_list = list()
			pr_map[merged_by] = pr_list
		else:
			pr_list = pr_map[merged_by]
		pr_list.append(pr)
	return pr_map


def create_prs(repository: str, merged_by_prs_map: dict, day: datetime.date):
	for author in merged_by_prs_map.keys():
		create_pr(repository, author, merged_by_prs_map[author], day)

def create_pr(repository: str, merged_by: str, prs: list, day: datetime.date):
	if len(prs) == 0:
		return
	print(f"Creating changelog PR for @{merged_by}")

	sample_pr = prs[0]
	base_branch = sample_pr["baseRefName"]
	pr_branch_name = create_pr_branch(day, merged_by, base_branch)
	pr_body, changelog_lines = generate_content(prs, merged_by)
	create_commit(changelog_lines)
	push_pr_branch(pr_branch_name)

	command = f"""gh pr create \
		--repo "{repository}" \
		--assignee "{merged_by}" \
		--base "{base_branch}" \
		--label "changelog-pr" \
		--title "chore: changelog updates for {day}, merged by @{merged_by}" \
		--body-file -
	"""

	proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	outs, errors = proc.communicate(input=pr_body.encode())
	if proc.returncode != 0:
		print(errors)
		exit(1)
	print(f"Created PR: {outs.decode()}")

def create_commit(changelog_lines: str):
	with open('.changes-pending.md', 'a') as changelog:
		changelog.write(changelog_lines)

	command = "git commit .changes-pending.md -m 'Add pending changelog entries'"
	proc = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE)
	_, errors = proc.communicate()
	if proc.returncode != 0:
		print(errors)
		exit(1)

def generate_content(prs: list, merged_by: str) -> (str, str):
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
	with open('CONTRIBUTORS.md', 'rt') as handle:
		line = handle.readline()
		while not ('##' in line and 'Contributors' in line):
			match = regex.match(line)
			if match:
				DEVELOPERS[match.group(2)] = match.group(1)
			line = handle.readline()

def create_pr_branch(day: datetime.date, author: str, base_branch: str) -> str:
	branch_name = f"changelog-updates-for-{day}-{author} {base_branch}"
	command = f"git checkout -b {branch_name}"
	proc = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE)
	_, errors = proc.communicate()
	if proc.returncode != 0:
		print(errors)
		exit(1)

	return branch_name

def push_pr_branch(branch_name: str):
	command = f"git push -u origin {branch_name}"
	proc = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE)
	_, errors = proc.communicate()
	if proc.returncode != 0:
		print(errors)
		exit(1)

def run(source_repository: str, target_repository: str, today: datetime.date):
	day = today - datetime.timedelta(days=1)
	prs = get_prs(source_repository, day)
	prs_length = len(prs)
	print(f"Found {prs_length} PRs")
	if prs_length == 0:
		return

	merged_by_prs_map = parse_prs(prs)
	create_prs(target_repository, merged_by_prs_map, day)

if __name__ == "__main__":
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
	today = datetime.datetime.now(datetime.timezone.utc).date()

	if len(sys.argv) > 1:
		source_repository = sys.argv[1]
	if len(sys.argv) > 2:
		target_repository = sys.argv[2]
	if len(sys.argv) > 3:
		today = datetime.date.fromisoformat(sys.argv[3])
	run(source_repository, target_repository, today)
