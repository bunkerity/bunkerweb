#!/bin/bash

helm repo add mattermost https://helm.mattermost.com
helm install -f mattermost-chart-values.yml mattermost mattermost/mattermost-team-edition
