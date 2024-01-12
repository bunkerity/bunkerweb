#!/usr/bin/env python
#@spartantri 2018

import sys
import argparse
import base64

parser = argparse.ArgumentParser()

UserAgent="ModSecurity CRS 3 Tests"
Accept="text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5"
AcceptCharset="ISO-8859-1,utf-8;q=0.7,*;q=0.7"
AcceptEncoding="gzip,deflate"
AcceptLanguage="en-us,en;q=0.5"
ContentType="application/x-www-form-urlencoded"
payloads=[]
skeletontest=0
Meta='''---
  meta:
    author: "spartantri"
    enabled: true
    name: "skeletonid.yaml"
    description: "Positive tests for rule skeletonid"
  tests:
'''

parser.add_argument('-a', action='store', dest='Addr', help='Target ip address',
                     default='127.0.0.1')
parser.add_argument('-p', action='store', dest='Port', help='Target port',
                     default='80')
parser.add_argument('-v', action='store', dest='Host', help='Target virtual host',
                     default='localhost')
parser.add_argument('-s', action='store', dest='skeleton', help='Skeleton file',
                     default='positivetest.yaml.skeleton')
parser.add_argument('-o', action='store', dest='output', help='output file',
                     default='')
parser.add_argument('-r', action='store', dest='ruleid', help='Rule id',
                     default='944310')
parser.add_argument('-k', action='store', dest='combined_payload', help='Keyword containing combined pipe separated payloads',
                     default='')
parser.add_argument('-i', action='append', dest='list_payload', help='Keyword containing individual payload',
                     default=[])
parser.add_argument('-c', action='store', dest='prefix', help='Prefix keyword for all payloads',
                     default='')
parser.add_argument('-e', action='store', dest='sufix', help='Sufix keyword for all payloads',
                     default='')
parser.add_argument('-b', action='store_true', dest='base64encode', help='Encode payload using Base64',
                     default=False)
parser.add_argument('-d', action='store_true', dest='demo', help='Print demo rules if no data is provided',
                     default=False)
parser.add_argument('-t', action='store_true', dest='test', help='Launch FTW and test output',
                     default=False)
parser.add_argument('-w', action='store', dest='author', help='Test author',
                     default='spartantri')
start_options = parser.parse_args()

if len(sys.argv)<2 and not start_options.demo:
    parser.print_usage()
    exit()

for p in start_options.combined_payload.split('|'):
    if p not in payloads:
        # print('Checking %s' % (p))
        if len(p)>0:
            payloads.append(''.join([start_options.prefix, p, start_options.sufix]))

for p in start_options.list_payload:
    payloads.append(''.join([start_options.prefix, p, start_options.sufix]))

if start_options.output=='':
    o=sys.stdout
else:
    o=open(start_options.output, 'w')

o.write(Meta.replace('skeletonid', start_options.ruleid).replace('spartantri', start_options.author))
for item in payloads:
    if start_options.base64encode:
        payload=base64.encodestring(item).replace('\n', '')
        #print payload
    else:
        payload=item
    with open(start_options.skeleton,'r') as f:
        for l in f:
            l=l.replace('skeletonid', start_options.ruleid)
            l=l.replace('skeletonkeyword', payload)
            l=l.replace('skeletondefaultaddr', start_options.Addr)
            l=l.replace('skeletondefaultport', start_options.Port)
            l=l.replace('skeletondefaulthost', start_options.Host)
            l=l.replace('skeletondefaultuseragent', UserAgent)
            l=l.replace('skeletondefaultacceptcharset', AcceptCharset)
            l=l.replace('skeletondefaultacceptencoding', AcceptEncoding)
            l=l.replace('skeletondefaultacceptlanguage', AcceptLanguage)
            l=l.replace('skeletondefaultcontenttype', ContentType)
            l=l.replace('skeletondefaultaccept', Accept)
            if 'skeletontest' in l:
                l=l.replace('skeletontest', str(skeletontest))
                skeletontest+=1
            o.write(l)

if start_options.output != '':
    print ('Generated %s rules to file %s' % (str(skeletontest), start_options.output))
    o.close()

#print('\nGenerated %s tests' % (str(skeletontest)))
