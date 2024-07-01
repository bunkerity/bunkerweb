#!/bin/bash
fname=$1

echo '{% extends "base.html" %}'
echo '{% block body %}'
#github-markup $fname
curl -H 'Content-Type: text/x-markdown' --data-binary @$fname https://api.github.com/markdown/raw
echo '{% end %}'
