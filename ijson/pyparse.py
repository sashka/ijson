# -*- coding:utf-8 -*-
from decimal import Decimal

from ijson import errors


WHITESPACE = ('\t', '\n', '\r', ' ')


class Reader(object):
    def __init__(self, f):
        self.f = f
        self.retchar = ''

    def read(self, *args):
        if not self.retchar:
            return self.f.read(*args)
        else:
            if args:
                args = list(args)
                args[0] -= len(self.retchar)
            retchar, self.retchar = self.retchar, ''
            return retchar + self.f.read(*args)

    def pushchar(self, char):
        assert self.retchar == ''
        self.retchar = char

    def nextchar(self):
        while True:
            char = self.read(1)
            if not char:
                raise errors.IncompleteJSONError()
            if char not in WHITESPACE:
                return char

def parse_value(f):
    char = f.nextchar()
    if char == 'n':
        if f.read(3) != 'ull':
            raise errors.JSONError('Unexpected symbol')
        yield ('null', None)
    elif char == 't':
        if f.read(3) != 'rue':
            raise errors.JSONError('Unexpected symbol')
        yield ('boolean', True)
    elif char == 'f':
        if f.read(4) != 'alse':
            raise errors.JSONError('Unexpected symbol')
        yield ('boolean', False)
    elif char == '-' or ('0' <= char <= '9'):
        number = char
        is_float = False
        while True:
            char = f.read(1)
            if '0' <= char <= '9':
                number += char
            elif char == '.':
                if is_float: # another '.'
                    raise errors.JSONError('Unexpected symbol')
                is_float = True
                number += char
            else:
                f.pushchar(char)
                break
        if number == '-':
            raise errors.JSONError('Unexpected symbol')
        yield ('number', Decimal(number) if is_float else int(number))
    elif char == '"':
        yield ('string', parse_string(f))
    elif char == '[':
        for event in parse_array(f):
            yield event
    else:
        raise errors.JSONError('Unexpected symbol')

def parse_string(f):
    result = u''
    while True:
        char = f.read(1)
        if not char:
            raise StopIteration
        if char == '"':
            break
        result += char
    return result

def parse_array(f):
    yield ('start_array', None)
    char = f.nextchar()
    if char != ']':
        f.pushchar(char)
        while True:
            for event in parse_value(f):
                yield event
            char = f.nextchar()
            if char == ']':
                break
            if char != ',':
                raise errors.JSONError('Unexpected symbol')
    yield ('end_array', None)

def basic_parse(f):
    f = Reader(f)
    for value in parse_value(f):
        yield value
    try:
        f.nextchar()
    except errors.IncompleteJSONError:
        pass
    else:
        raise errors.JSONError('Additional data')
