import re
from sys import intern

import tokens

# language defaults
BLOCK_START_STRING = '{%'
BLOCK_END_STRING = '%}'
COMMENT_START_STRING = '{#'
COMMENT_END_STRING = '#}'
VARIABLE_START_STRING = '{{'
VARIABLE_END_STRING = '}}'

operators = {
    '+':    tokens.ADD,
    '-':    tokens.SUB,
    '/':    tokens.DIV,
    '*':    tokens.MUL,
    '//':   tokens.FLOOR_DIV,
    '**':   tokens.POW,
    '=':    tokens.ASSIGN,
    '==':   tokens.EQ,
    '!=':   tokens.NE,
    '>=':   tokens.GTEQ,
    '<=':   tokens.LTEQ,
    '>':    tokens.GT,
    '<':    tokens.LT,
    '(':    tokens.LPAREN,
    '[':    tokens.LBRACKET,
    '{':    tokens.LBRACE,
    ')':    tokens.RPAREN,
    ']':    tokens.RBRACKET,
    '}':    tokens.RBRACE,
    ':':    tokens.COLON,
    ';':    tokens.SEMICOLON,
    '.':    tokens.DOT,
    '~':    tokens.TILDE,
    '|':    tokens.PIPE,
    ',':    tokens.COMMA,
}
reversed_operators = dict((v, k) for k, v in operators.items())

name_re = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')
string_re = re.compile(r"('([^'\\]*(?:\\.[^'\\]*)*)'"
                       r'|"([^"\\]*(?:\\.[^"\\]*)*)")', re.S)
integer_re = re.compile(r'\d+')
float_re = re.compile(r'(?<!\.)\d+\.\d+')
whitespace_re = re.compile(r'\s+', re.U)
newline_re = re.compile(r'(\r\n|\r|\n)')
operator_re = re.compile('|'.join(re.escape(o) for o in 
                        sorted(operators, key=lambda x: -len(x))))

ignored_tokens = set([tokens.WHITESPACE, tokens.COMMENT, 
                        tokens.COMMENT_BEGIN, tokens.COMMENT_END])
ignore_if_empty = set([tokens.DATA, tokens.COMMENT, tokens.WHITESPACE])

class Failure(Exception): pass
class TemplateSyntaxError(Exception): pass

def raise_if_failure(obj):
    if isinstance(obj, Failure):
        raise obj


class Token:
    def __init__(self, lineno, type, value):
        """Represents a token"""
        self.lineno = lineno
        self.type = type
        self.value = value

    def __repr__(self):
        return 'Token(%r, %r, %r)' % (
            self.lineno,
            self.type,
            self.value
        )
    
    def test(self, expr):
        """Compares expressions like `name:value` or `name` with the token"""
        if ':' in expr:
            return expr == '{0}:{1}'.format(self.type, self.value)
        return self.type == expr


class TokenStreamIterator:
    def __init__(self, stream):
        """Implements an iterator for a `TokenStream`"""
        self.stream = stream

    def __next__(self):
        rv = self.stream.current
        if rv.type == tokens.EOF:
            self.stream.close()
            raise StopIteration()
        next(self.stream)
        return rv

    def __iter__(self):
        return self


class TokenStream:
    def __init__(self, generator):
        """A token stream with `.current` as the current active token"""
        self._iter = generator
        self.current = Token(0, tokens.INITIAL, '')
        self.closed = False
        next(self)

    def __next__(self):
        """Returns the the current token and moves on to the next one"""
        if self.closed:
            return self.current
        rv = self.current
        try:
            self.current = next(self._iter)
        except StopIteration:
            self.close()
        return rv

    def __iter__(self):
        return TokenStreamIterator(self)

    def expect(self, expr):
        """Tests the current with `expr` using `token.test(expr)`"""
        assert self.current.test(expr), 'expected %r got %r' % (expr, self.current.type)
        return next(self)

    def skip_if(self, expr):
        if self.current.test(expr):
            next(self)
            return True
        return False

    def close(self):
        self.current = Token(self.current.lineno, tokens.EOF, '')
        self._iter = None
        self.closed = True

    @property
    def lineno(self):
        return self.current.lineno


class Lexer:
    def __init__(self, environment):
        e = re.escape
        c = lambda x: re.compile(x, re.M | re.S)
        self.environment = environment

        # tag lexing rules
        self.tag_rules = [
            (name_re, tokens.NAME, None),
            (string_re, tokens.STRING, None),
            (integer_re, tokens.INTEGER, None),
            (float_re, tokens.FLOAT, None),
            (operator_re, tokens.OPERATOR, None),
            (whitespace_re, tokens.WHITESPACE, None),
        ]

        # root lexing rules
        self.root_tag_rules = [
            ('block', r'%s' % e(BLOCK_START_STRING)),
            ('comment', r'%s' % e(COMMENT_START_STRING)),
            ('variable', r'%s' % e(VARIABLE_START_STRING)),
        ]

        # directives
        # latest_match: [(regex, regex_groups, new_state)]
        self.rules = {
            'root': [
                (c('(.*?)(?:%s)' % '|'.join(
                    [r'(?P<%s_begin>%s)' % (n, r) 
                        for n, r in self.root_tag_rules]
                        )), (tokens.DATA, '#bygroup'), '#bygroup'),
                (c('.+'), tokens.DATA, None)
            ],
            tokens.COMMENT_BEGIN: [
                (c(r'(.*?)(%s)' % e(COMMENT_END_STRING)),
                    (tokens.COMMENT, tokens.COMMENT_END), '#pop'),
                (c(r'(.+)'), Failure('Expected %s' % tokens.COMMENT_END), None)
            ],
            tokens.BLOCK_BEGIN: [
                (c(r'(%s)' % e(BLOCK_END_STRING)), tokens.BLOCK_END, '#pop')
            ] + self.tag_rules,
            tokens.VARIABLE_BEGIN: [
                (c(r'(%s)' % e(VARIABLE_END_STRING)), tokens.VARIABLE_END, '#pop')
            ] + self.tag_rules,
        }
    
    def tokenize(self, source):
        """Returns a TokenStream"""
        stream_generator = self.tokenizer(source)
        # for t in self.wrap(stream_generator):
        #     print(t)
        return TokenStream(self.wrap(stream_generator))

    def tokenizer(self, source):
        source = '\n'.join(source.splitlines())
        lineno = 1
        pos = 0
        stack = ['root']
        current_rule = self.rules[stack[-1]]
        brackets_stack = []

        while 1:
            for regex, group_tokens, next_state in current_rule:
                m = regex.match(source, pos)
                if not m:
                    continue
                
                # if there's a bracket mismatch, we continue scanning
                # with the operator rule instead of processing the _end token
                if brackets_stack and group_tokens in (tokens.BLOCK_END, 
                    tokens.COMMENT_END, tokens.VARIABLE_END):
                    # print('skippin')
                    continue

                if isinstance(group_tokens, tuple):
                    for idx, token in enumerate(group_tokens):
                        raise_if_failure(token)
                        # bygroups are resolved through match group names
                        if token == '#bygroup':
                            for k, v in m.groupdict().items():
                                if v is not None:
                                    yield lineno, k, v
                                    lineno += v.count('\n')
                                    break
                            else:
                                raise RuntimeError("couldn't resolve bygroup" 
                                    "dynamically in line %d" % lineno)
                        else:
                            # yield normal data as is
                            data = m.group(idx + 1)
                            if data or token not in ignore_if_empty:
                                yield lineno, token, data
                            lineno += data.count('\n')
                else:
                    raise_if_failure(group_tokens)
                    data = m.group()
                    closing_brackets = {
                        '{': '}',
                        '[': ']',
                        '(': ')'
                    }
                    # validate bracket pairs
                    if group_tokens == 'operator':
                        if data in closing_brackets:
                            brackets_stack.append(closing_brackets[data])
                        elif data in closing_brackets.values():
                            if not brackets_stack:
                                raise TemplateSyntaxError('unexpected character %s'
                                    ' in line %d' % (data, lineno))

                            expected_ch = brackets_stack.pop()
                            if data != expected_ch:
                                raise TemplateSyntaxError('expected %s instead of'
                                    ' %s in line %d' % (expected_ch, data, lineno))

                    if data or group_tokens not in ignore_if_empty:
                        yield lineno, group_tokens, data
                    lineno += data.count('\n')
                # handle the next state
                pos2 = m.end()
                if next_state is not None:
                    if next_state == '#pop':
                        stack.pop()
                    elif next_state == '#bygroup':
                        for k, v in m.groupdict().items():
                            if v is not None:
                                stack.append(k)
                                break
                        else:
                            raise RuntimeError("couldn't resolve bygroup" 
                                "dynamically in line %s" % lineno)
                    else:
                        stack.append(next_state)
                    current_rule = self.rules[stack[-1]]
                # we have not moved forward
                elif pos2 == pos:
                    raise RuntimeError("%r couldn't match any strings" % regex)
                pos = pos2
                break
            # if we didn't break out, we're at the eof or in an error state
            else:
                if pos >= len(source):
                    return
                raise TemplateSyntaxError('unexpected char %s in line %d' % (source[pos], lineno))

    def wrap(self, stream_generator):
        """Returns a generator wrapping the tokens returned by
        `tokenizer` as `Token` instances"""
        for lineno, token, value in stream_generator:
            if token in ignored_tokens:
                continue
            elif token == tokens.OPERATOR:
                token = operators[value]
            elif token == tokens.INTEGER:
                value = int(value)
            elif token == tokens.FLOAT:
                value = float(value)
            elif token == tokens.STRING:
                value = value[1:-1]
            yield Token(lineno, token, value)