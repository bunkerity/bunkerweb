#!/bin/sh

function job_log() {
	when="$(date +[%d/%m/%Y %H:%M:%S])"
	what="$1"
	echo "$when $what" >> /var/log/jobs.log
}

