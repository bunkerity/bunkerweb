#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This is designed to convert 2.x CRS ID numbering to 3.x CRS numbering"""
from __future__ import print_function
import csv
import argparse
import os
import sys

def main():
    """Main function that contains all the logic to relabel CRS IDs"""

    id_translation_file = os.path.join(sys.path[0], "IdNumbering.csv")

    if not os.path.isfile(id_translation_file):
        sys.stderr.write("We were unable to locate the ID translation CSV (idNumbering.csv) \
            please place this is the same directory as this script\n")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="A program that takes in an exceptions file \
        and renumbers all the ID to match OWASP CRS 3 numbers. Output will be directed to STDOUT.")
    parser.add_argument("-f", "--file", required=True, action="store", dest="fname", \
        help="the file to be renumbered")
    args = parser.parse_args()

    if not os.path.isfile((args.fname).encode('utf8')):
        sys.stderr.write("We were unable to find the file you were trying to update the ID numbers \
            in, please check your path\n")
        sys.exit(1)

    fcontent = ""

    try:
        update_file = open((args.fname).encode('utf-8'), "r")
        try:
            fcontent = update_file.read()
        finally:
            update_file.close()
    except IOError:
        sys.stderr.write("There was an error opening the file you were trying to update")

    if fcontent != "":
        # CSV File
        id_csv_file = open(id_translation_file, 'rt')
        try:
            reader = csv.reader(id_csv_file)
            for row in reader:
                fcontent = fcontent.replace(row[0], row[1])
        finally:
            id_csv_file.close()
    print(fcontent)

if __name__ == "__main__":
    main()
