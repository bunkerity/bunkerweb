"""Common code for generating the test code to validate mbedtls_ssl_session_reset().
"""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

import enum
import os
import re
import sys
import typing
import argparse
from typing import Dict, Iterator, List, Tuple, FrozenSet

from . import c_parsing_helper
from . import typing_util
from . import build_tree

class ResetBehavior(enum.Enum):
    KEEP = 0        # Kept unchanged before/after the reset
    RESET = 1       # Returned to the initial state (which is not necessarily 0)
    REALLOCATE = 2  # Pointer that gets reallocated
    IGNORE = 3      # Ignored field
    SPECIAL = 4

class ElementType(enum.Enum):
    SCALAR = 0
    POINTER = 1
    ARRAY = 2
    NAMED_STRUCTURE = 3
    IGNORE = 4
    SPECIAL = 5

class FieldsInfo(typing.NamedTuple):
    """Expected reset behavior for the fields of the structure."""
    rules: Dict[str, ResetBehavior]
    special: Dict[str, List[str]]
    # The script isn't capable to identify named structures (ex: dtls_srtp_info)
    # so we keep an explicit list of them.
    named_structures: FrozenSet[str]

class CField():
    # pylint: disable=too-few-public-methods
    """Information about one field of a C struct."""
    name: str
    conditional: List[str]
    element_type: ElementType

    def __init__(self, name: str, conditionals: List[str], element_type: ElementType):
        self.name = name
        self.conditionals = conditionals.copy()
        self.element_type = element_type

    def check_value(self) -> List[str]:
        raise Exception(f'Class {self.__class__.__name__} cannot handle entries'
                        f'of type {self.element_type}')

class CFieldIgnore(CField):
    # pylint: disable=too-few-public-methods
    """Explicitly ignored field."""
    def check_value(self) -> List[str]:
        return [f'/* {self.name} is ignored */']

class CFieldKeep(CField):
    # pylint: disable=too-few-public-methods
    """Field kept unchanged."""
    def check_value(self) -> List[str]:
        if self.element_type == ElementType.SCALAR:
            return [f'TEST_EQUAL(before->{self.name}, after->{self.name});']
        elif self.element_type == ElementType.POINTER:
            return [f'TEST_ASSERT(before->{self.name} == after->{self.name});']
        elif self.element_type == ElementType.ARRAY:
            return [f'TEST_MEMORY_COMPARE(before->{self.name}, '
                    f'sizeof(before->{self.name}), after->{self.name}, '
                    f'sizeof(after->{self.name}));']
        elif self.element_type == ElementType.NAMED_STRUCTURE:
            return [f'TEST_MEMORY_COMPARE(&(before->{self.name}), '
                    f'sizeof(before->{self.name}), &(after->{self.name}), '
                    f'sizeof(after->{self.name}));']
        return super().check_value()

class CFieldReset(CField):
    # pylint: disable=too-few-public-methods
    """Field returned to the intial state."""
    def check_value(self) -> List[str]:
        if (self.element_type == ElementType.SCALAR) or (self.element_type == ElementType.POINTER):
            return [f'TEST_ASSERT(after->{self.name} == initial.{self.name});']
        elif self.element_type == ElementType.ARRAY:
            return [f'TEST_MEMORY_COMPARE(after->{self.name}, '
                    f'sizeof(after->{self.name}), initial.{self.name}, '
                    f'sizeof(initial.{self.name}));']
        elif self.element_type == ElementType.NAMED_STRUCTURE:
            return [f'TEST_MEMORY_COMPARE(&(after->{self.name}), '
                    f'sizeof(after->{self.name}), &(initial.{self.name}), '
                    f'sizeof(initial.{self.name}));']
        return super().check_value()

class CFieldReallocate(CField):
    # pylint: disable=too-few-public-methods
    """Pointer (might be) reallocated during reset."""
    def check_value(self) -> List[str]:
        if self.element_type == ElementType.POINTER:
            return [f'TEST_ASSERT(after->{self.name} != NULL);']
        return super().check_value()

class CFieldSpecial(CField):
    # pylint: disable=too-few-public-methods
    """Field with a custom check."""
    custom_behavior: List[str]

    def __init__(self, name: str, conditional: List[str], element_type: ElementType,
                 custom_behavior: List[str]):
        self.custom_behavior = custom_behavior
        super().__init__(name, conditional, element_type)

    def check_value(self) -> List[str]:
        return self.custom_behavior

class CStruct:
    # pylint: disable=too-few-public-methods
    """Information about the fields of a C struct."""

    _PREPROCESSOR_RE = re.compile(r'\s*#\s*(\w+)\s*(.*)')
    _STRUCT_RE = re.compile(r'struct\s+(\w+)\s*{')
    _FIELD_RE = re.compile(r'\s*([^;]+);')
    _PRIVATE_FIELD_RE = re.compile(r'MBEDTLS_PRIVATE\((\w+)\)')
    _BARE_FIELD_RE = re.compile(r'[\t *](\w+)\Z')
    _NON_BLANK_RE = re.compile(r'.*\S')

    def _get_element_type(self, name: str, declaration: str) -> ElementType:
        """Return structure field type based on either its name or the fact
        that it belongs to the list of special symbols/named structures"""
        # Check for fields with custom check rules
        if name in self.fields_info.special:
            return ElementType.SPECIAL
        # Check for named structures
        if name in self.fields_info.named_structures:
            return ElementType.NAMED_STRUCTURE
        # Check for pointer
        if '*' in declaration:
            return ElementType.POINTER
        # Check for array
        if '[' in declaration:
            return ElementType.ARRAY
        # If we get here then the field is a scalar
        return ElementType.SCALAR

    def _parse_field(self, declaration: str, conditionals: List[str]) -> CField:
        """Return the CField object describing the given field declaration."""
        # Note that this simplistic parsing finds fields in inline
        # sub-structs, unions and enums.
        m = self._PRIVATE_FIELD_RE.search(declaration)
        if not m:
            m = self._BARE_FIELD_RE.search(declaration)
        if not m:
            raise Exception(f'Field name not found in "{declaration}"')
        name = m.group(1)
        # Get the expected behavior on reset
        if name not in self.fields_info.rules:
            raise Exception(f'Field {name} does not have an associated behavior')
        behavior = self.fields_info.rules[name]
        element_type = self._get_element_type(name, declaration)
        if behavior == ResetBehavior.SPECIAL:
            return CFieldSpecial(name, conditionals, element_type,
                                 self.fields_info.special[name])
        elif behavior == ResetBehavior.KEEP:
            return CFieldKeep(name, conditionals, element_type)
        elif behavior == ResetBehavior.REALLOCATE:
            return CFieldReallocate(name, conditionals, element_type)
        elif behavior == ResetBehavior.IGNORE:
            return CFieldIgnore(name, conditionals, element_type)
        elif behavior == ResetBehavior.RESET:
            return CFieldReset(name, conditionals, element_type)
        else:
            raise Exception(f'Unhandled behavior {behavior}')

    @staticmethod
    def _continue_parsing_preprocessor(arguments: str,
                                       lines: Iterator[Tuple[int, str]]) -> str:
        """Append continuation lines of preprocesssor directive."""
        while True:
            try:
                line_content = next(lines)[1]
                arguments = arguments + '\n' + line_content
            except StopIteration:
                raise Exception('Unexpected end of file reached while '
                                ' parsing a C preprocessor directive')
            if not line_content.endswith('\\'):
                break
        return arguments

    def _structure_fields(self,
                          lines: Iterator[Tuple[int, str]],
                          struct_name: str) -> Iterator[CField]:
        """Yield a CField object for each field of the given structure."""
        # pylint: disable=too-many-branches
        found_start = False
        for num, line in lines:
            m = self._STRUCT_RE.match(line)
            if m and m.group(1) == struct_name:
                found_start = True
                break
        if not found_start:
            raise Exception(f'Definition of struct {struct_name} not found')
        conditionals: List[str] = []
        for num, line in lines:
            if line.startswith('}'):
                return
            m = self._PREPROCESSOR_RE.match(line)
            if m:
                # If the preprocessor directives are included in parentheses (ex:
                # "(defined(AAA) && defined(BBB))") then 'line' contains the full directive
                # including new lines (if present) so we can just copy that.
                # If instead outer parentheses are missing, ex: "defined(AAA) && defined(BBB)"
                # then parsing stops at the end of the line so we need to keep parsing
                # manually if there is a "\" at the end of the line.
                if line.endswith('\\'):
                    arguments = m.group(2)
                    arguments = self._continue_parsing_preprocessor(arguments, lines)
                    one_conditional = '#if ' + arguments
                else:
                    one_conditional = line
                one_conditional = one_conditional + '\n'
                directive = m.group(1)
                if directive == 'if':
                    conditionals.append(one_conditional)
                elif directive == 'endif':
                    del conditionals[-1]
                else:
                    raise Exception(f'Unsupported directive #{directive} at line {num}')
                continue
            m = self._FIELD_RE.match(line)
            if m:
                yield self._parse_field(m.group(1), conditionals)
                continue
            m = self._NON_BLANK_RE.match(line)
            if m:
                raise Exception(f'Failed to parse non-empty line {num}. Content is: {line}')
        raise Exception(f'End of definition of struct {struct_name} not found')

    def _check_special_fields(self):
        """Ensure that all the entries FieldsInfo.rules that are given a SPECIAL
        behavior also have the corresponding entry in FieldsInfo.special
        (and viceversa)"""
        in_rules = frozenset(name for name in self.fields_info.rules
                             if self.fields_info.rules[name] == ResetBehavior.SPECIAL)
        in_special = frozenset(self.fields_info.special)
        if in_rules != in_special:
            raise Exception(f'Fields with SPECIAL rule in FieldsInfo.rules but '
                            f'not listed in FieldsInfo.special: {in_rules - in_special}. '
                            f'Fields listed FieldsInfo.special, but not given a'
                            f'SPECIAL rule in FieldsInfo.rules: {in_special - in_rules}.')

    def _check_rules_struct_fields_matching(self):
        """Ensure that for each field of the given FieldsInfo.rules there is
        an entry in the parsed C structure and viceversa"""
        given = frozenset(name for name in self.fields_info.rules)
        parsed = frozenset(field.name for field in self.fields)
        if given != parsed:
            raise Exception(f'Fields found in the C struct but not given a '
                            f'reset behavior: {parsed - given}. '
                            f'Fields given a reset behavior but not found in '
                            f'the C struct: {given - parsed}')

    def __init__(self, file_name: str, struct_name: str,
                 fields_info: FieldsInfo) -> None:
        """Parse a structure definition in a C source file."""
        self.fields_info = fields_info
        self._check_special_fields()
        lines = c_parsing_helper.read_logical_lines(file_name)
        self.fields = list(self._structure_fields(lines, struct_name))
        self._check_rules_struct_fields_matching()


class SSLContextStruct(CStruct):
    # pylint: disable=too-few-public-methods
    """Information about the fields of struct mbedtls_ssl_context."""

    def __init__(self, fields_info: FieldsInfo) -> None:
        super().__init__('include/mbedtls/ssl.h', 'mbedtls_ssl_context',
                         fields_info)

    def write_check_function(self, out: typing_util.Writable) -> None:
        """Write the generated context-checking function to the output."""
        out.write(f"""\
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

/*
 * The following function was automatically generated through the script
 * {sys.argv[0]}.
 */

#include <test/ssl_helpers.h>
#include <test/ssl_helpers_internal.h>
#include "mbedtls/psa_util.h"
#include <test/macros.h>

#include <limits.h>

#if defined(MBEDTLS_SSL_TLS_C)

int mbedtls_test_ssl_check_context_after_session_reset(const mbedtls_ssl_context *before,
                                                       const mbedtls_ssl_context *after)
{{
    mbedtls_ssl_context initial;
    int ret = -1;

    /* Create a freshly initialized SSL context*/
    memset(&initial, 0, sizeof(initial));
    mbedtls_ssl_init(&initial);
    TEST_EQUAL(mbedtls_ssl_setup(&initial, after->conf), 0);

    /* *INDENT-OFF* */
""")
        for field in self.fields:
            if len(field.conditionals) > 0:
                out.write('\n'.join(field.conditionals))
            for check_line in field.check_value():
                out.write(f'    {check_line}\n')
            if len(field.conditionals) > 0:
                out.write('#endif\n' * len(field.conditionals))
        out.write(f"""\
    /* *INDENT-ON* */

    ret = 0;

exit:
    mbedtls_ssl_free(&initial);

    return ret;
}}

#endif /* MBEDTLS_SSL_TLS_C */
""")


def main(fields_info: FieldsInfo):
    if not build_tree.looks_like_mbedtls_root(os.curdir):
        raise Exception("The script must be launched from the root path of Mbed TLS")
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-o', dest='output_file',
                            help='Generated output file',
                            default='tests/src/ssl_context_reset_verifier.c')
    parsed_args = arg_parser.parse_args()

    output_file = parsed_args.output_file
    with open(output_file, 'wt') as out:
        ssl_context = SSLContextStruct(fields_info)
        ssl_context.write_check_function(out)
