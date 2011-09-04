from decimal import Decimal
import re


BUFSIZE = 64 * 1024
NONWS = re.compile(r'\S')
STRTERM = re.compile(r'["\\]')


class JSONError(Exception):
    pass

class IncompleteJSONError(JSONError):
    def __init__(self):
        super(IncompleteJSONError, self).__init__('Incomplete or empty JSON data')

class Reader(object):
    def __init__(self, f):
        self.f = f
        self.buffer = bytearray()
        self.pos = 0

    def read(self, count=None):
        if count is None:
            result = str(sef.buffer[self.pos:] + self.f.read())
            self.buffer = bytearray()
            self.pos = 0
            return result
        if count <= len(self.buffer) - self.pos:
            start = self.pos
            self.pos += count
            return str(self.buffer[start:self.pos])
        if count > len(self.buffer) - self.pos:
            over = count - (len(self.buffer) - self.pos)
            self.newbuffer = bytearray(self.f.read(BUFSIZE))
            result = str(self.buffer[self.pos:] + self.newbuffer[:over])
            self.buffer = self.newbuffer
            self.pos = over
            return result

    def pushchar(self, char):
        self.buffer.insert(self.pos, char)

    def nextchar(self):
        while True:
            match = NONWS.search(self.buffer, self.pos)
            if match:
                self.pos = match.start() + 1
                return chr(self.buffer[match.start()])
            self.buffer = bytearray(self.f.read(BUFSIZE))
            self.pos = 0
            if not len(self.buffer):
                raise IncompleteJSONError()

    def readuntil(self, pattern):
        result = bytearray()
        terminator = None
        while True:
            match = pattern.search(self.buffer, self.pos)
            if match:
                terminator = chr(self.buffer[match.start()])
                result.extend(self.buffer[self.pos:match.start()])
                self.pos = match.start() + 1
                break
            result.extend(self.buffer)
            self.buffer = bytearray(self.f.read(BUFSIZE))
            self.pos = 0
            if not self.buffer:
                break
        return str(result), terminator

def parse_value(f):
    char = f.nextchar()
    if char == 'n':
        if f.read(3) != 'ull':
            raise JSONError('Unexpected symbol')
        yield ('null', None)
    elif char == 't':
        if f.read(3) != 'rue':
            raise JSONError('Unexpected symbol')
        yield ('boolean', True)
    elif char == 'f':
        if f.read(4) != 'alse':
            raise JSONError('Unexpected symbol')
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
                    raise JSONError('Unexpected symbol')
                is_float = True
                number += char
            else:
                if char:
                    f.pushchar(char)
                break
        if number == '-':
            raise JSONError('Unexpected symbol')
        yield ('number', Decimal(number) if is_float else int(number))
    elif char == '"':
        yield ('string', parse_string(f))
    elif char == '[':
        for event in parse_array(f):
            yield event
    elif char == '{':
        for event in parse_object(f):
            yield event
    else:
        raise JSONError('Unexpected symbol')

def parse_string(f):
    result = ''
    while True:
        chunk, terminator = f.readuntil(STRTERM)
        if not terminator:
            raise IncompleteJSONError()
        result += chunk
        if terminator == '"':
            break
        if terminator == '\\':
            result += terminator + f.read(1)
    return result.decode('unicode-escape')

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
                raise JSONError('Unexpected symbol')
    yield ('end_array', None)

def parse_object(f):
    yield ('start_map', None)
    while True:
        char = f.nextchar()
        if char != '"':
            raise JSONError('Unexpected symbol')
        yield ('map_key', parse_string(f))
        char = f.nextchar()
        if char != ':':
            raise JSONError('Unexpected symbol')
        for event in parse_value(f):
            yield event
        char = f.nextchar()
        if char == '}':
            break
        if char != ',':
            raise JSONError('Unexpected symbol')
    yield ('end_map', None)

def basic_parse(f):
    f = Reader(f)
    for value in parse_value(f):
        yield value
    try:
        f.nextchar()
    except IncompleteJSONError:
        pass
    else:
        raise JSONError('Additional data')

def parse(*args, **kwargs):
    '''
    An iterator returning events from a JSON being parsed. This iterator
    provides the context of parser events accompanying them with a "prefix"
    value that contains the path to the nested elements from the root of the
    JSON document.

    For example, given this document:

        {
            "array": [1, 2],
            "map": {
                "key": "value"
            }
        }

    the parser would yield events:

        ('', 'start_map', None)
        ('', 'map_key', 'array')
        ('array', 'start_array', None)
        ('array.item', 'number', 1)
        ('array.item', 'number', 2)
        ('array', 'end_array', None)
        ('', 'map_key', 'map')
        ('map', 'start_map', None)
        ('map', 'map_key', 'key')
        ('map.key', 'string', u'value')
        ('map', 'end_map', None)
        ('', 'end_map', None)

    For the list of all available event types refer to `basic_parse` function.

    Parameters:

    - f: a readable file-like object with JSON input
    - allow_comments: tells parser to allow comments in JSON input
    - check_utf8: if True, parser will cause an error if input is invalid utf-8
    - buf_size: a size of an input buffer
    '''
    path = []
    for event, value in basic_parse(*args, **kwargs):
        if event == 'map_key':
            prefix = '.'.join(path[:-1])
            path[-1] = value
        elif event == 'start_map':
            prefix = '.'.join(path)
            path.append(None)
        elif event == 'end_map':
            path.pop()
            prefix = '.'.join(path)
        elif event == 'start_array':
            prefix = '.'.join(path)
            path.append('item')
        elif event == 'end_array':
            path.pop()
            prefix = '.'.join(path)
        else: # any scalar value
            prefix = '.'.join(path)

        yield prefix, event, value


class ObjectBuilder(object):
    '''
    Incrementally builds an object from JSON parser events. Events are passed
    into the `event` function that accepts two parameters: event type and
    value. The object being built is available at any time from the `value`
    attribute.

    Example:

        from StringIO import StringIO
        from ijson.parse import basic_parse
        from ijson.utils import ObjectBuilder

        builder = ObjectBuilder()
        f = StringIO('{"key": "value"})
        for event, value in basic_parse(f):
            builder.event(event, value)
        print builder.value

    '''
    def __init__(self):
        def initial_set(value):
            self.value = value
        self.containers = [initial_set]

    def event(self, event, value):
        if event == 'map_key':
            self.key = value
        elif event == 'start_map':
            map = {}
            self.containers[-1](map)
            def setter(value):
                map[self.key] = value
            self.containers.append(setter)
        elif event == 'start_array':
            array = []
            self.containers[-1](array)
            self.containers.append(array.append)
        elif event == 'end_array' or event == 'end_map':
            self.containers.pop()
        else:
            self.containers[-1](value)

def items(file, prefix):
    '''
    Iterates over a file objects and everything found under given prefix as
    as native Python objects.
    '''
    parser = iter(parse(file))
    try:
        while True:
            current, event, value = parser.next()
            if current == prefix:
                builder = ObjectBuilder()
                if event in ('start_map', 'start_array'):
                    end_event = event.replace('start', 'end')
                    while (current, event) != (prefix, end_event):
                        builder.event(event, value)
                        current, event, value = parser.next()
                else:
                    builder.event(event, value)
                yield builder.value
    except StopIteration:
        pass
