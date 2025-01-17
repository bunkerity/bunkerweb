#!/usr/bin/env bash

valgrind --tool=massif
valgrind --show-leak-kinds=all --leak-check=full ./test
