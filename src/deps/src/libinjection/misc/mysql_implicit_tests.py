#!/usr/bin/python

mysql_ops = (
    'AND',
    '&&',
    '=',
    '&',
    '|',
    '^',
    'DIV',
    '/',
    '<=>',
    '>=',
    '>',
    '<<',
    '<=',
    '<',
    'LIKE',
    '-',
    '%',
    'MOD',
    '!=',
    '<>',
    'NOT LIKE',
    'NOT REGEXP',
    'OR',
    '||',
    '+',
    'REGEXP',
    '>>',
    'RLIKE',
    'NOT RLIKE',
    'SOUNDS LIKE',
    '*',
    'XOR'
)

print '# mysql implicit conversions tests'

for op in mysql_ops:
    if op == '+':
        op = '%2B'

    print "A' {0} 'B".format(op)
    print "A '{0}' B".format(op)
    print "'{0}'".format(op)
    print "' {0} '".format(op)
