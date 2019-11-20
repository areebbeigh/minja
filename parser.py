import nodes
import tokens
from lexer import reversed_operators
from utils import concat

_statement_keywords = ('for', 'with', 'if', 'block', 'extends')
_compare_operators = ('eq', 'neq', 'geq', 'leq', 'gt', 'lt')
_math_nodes = {
    tokens.ADD:       nodes.Add,
    tokens.SUB:       nodes.Sub,
    tokens.MUL:       nodes.Mul,
    tokens.DIV:       nodes.Div,
    tokens.FLOOR_DIV: nodes.FloorDiv,
    tokens.POW:       nodes.Pow
}

class Parser:
    def __init__(self, environment, source):
        self.environment = environment
        self.token_stream = environment.tokenize(source)

    def fail(self, msg, lineno):
        assert (msg, lineno) is False

    def unknown_tag(self, lineno):
        assert lineno is False

    def is_tuple_end(self, extra_end_rules=None):
        if self.token_stream.current.type in (tokens.VARIABLE_END, 
            tokens.BLOCK_END, tokens.RPAREN):
            return True
        if extra_end_rules is not None:
            return any(map(self.token_stream.current.test, extra_end_rules))
        return False

    def parse_statements(self, end_tokens=None, drop_needle=True):
        self.token_stream.expect(tokens.BLOCK_END)
        rv = self.subparse(end_tokens)
        if self.token_stream.closed:
            self.fail('unexpected end of file', self.token_stream.lineno)
        if drop_needle:
            next(self.token_stream)
        return rv

    def parse_statement(self):
        token = self.token_stream.current
        if token.type != tokens.NAME:
            self.fail('tag name expected', token.lineno)

        if token.value in _statement_keywords:
            method = 'parse_' + token.value.lower()
            method = getattr(self, method)
            return method()

        self.unknown_tag(token.lineno)

    def parse_extends(self):
        lineno = self.token_stream.expect('name:extends').lineno
        template = self.parse_expression()
        return nodes.Extends(template, lineno=lineno)

    def parse_if(self):
        node = rv = nodes.If(lineno=self.token_stream.expect('name:if').lineno)
        while True:
            node.test = self.parse_tuple()
            node.body = self.parse_statements(end_tokens=('name:elif',
                                                'name:else',
                                                'name:endif'),
                                                drop_needle=False)
            node.elif_ = []
            node.else_ = []
            token = next(self.token_stream)
            if token.test('name:elif'):
                node = nodes.If(lineno=token.lineno)
                rv.elif_.append(node)
                continue
            elif token.test('name:else'):
                rv.else_ = self.parse_statements(end_tokens=('name:endif',))
                break
            else:
                break
        return rv

    def parse_for(self):
        lineno = self.token_stream.expect('name:for').lineno
        target = self.parse_assign_target(extra_end_rules=('name:in',))
        self.token_stream.expect('name:in')
        iter = self.parse_tuple()
        body = self.parse_statements(end_tokens=('name:endfor',
                                                    'name:else'),
                                                drop_needle=False)
        test = None
        if self.token_stream.skip_if('name:if'):
            test = self.parse_expression()
        token = next(self.token_stream)
        if token.test('name:else'):
            else_ = self.parse_statements(end_tokens=('name:endfor',))
        else:
            else_ = []
        return nodes.For(target, iter, body, test, else_, lineno=lineno)

    def parse_block(self):
        lineno = self.token_stream.expect('name:block').lineno
        name = self.token_stream.expect('name').value
        body = self.parse_statements(end_tokens=('name:endblock',))
        self.token_stream.skip_if('name:' + name)
        return nodes.Block(name, body, lineno=lineno)

    def parse_with(self):
        lineno = next(self.token_stream).lineno
        targets = []
        values = []
        while self.token_stream.current.type is not tokens.BLOCK_END:
            if targets:
                self.token_stream.expect(tokens.COMMA)
            target = self.parse_assign_target()
            self.token_stream.expect(tokens.ASSIGN)
            value = self.parse_expression()
            target.set_ctx('param')
            targets.append(target)
            values.append(value)

        body = self.parse_statements(('name:endwith',))
        return nodes.With(targets, values, body, lineno=lineno)

    def parse_assign_target(self, extra_end_rules=None):
        target = self.parse_tuple(simplified=True, 
                                extra_end_rules=extra_end_rules)
        # assert target.can_assign()
        target.set_ctx('store')
        return target

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        lineno = self.token_stream.lineno
        left = self.parse_and()
        while self.token_stream.current.test('name:or'):
            next(self.token_stream)
            right = self.parse_and()
            left = nodes.Or(left, right, lineno)
            lineno = self.token_stream.lineno
        return left

    def parse_and(self):
        lineno = self.token_stream.lineno
        left = self.parse_not()
        while self.token_stream.current.test('name:and'):
            next(self.token_stream)
            right = self.parse_not()
            left = nodes.And(left, right, lineno)
            lineno = self.token_stream.lineno
        return left
    
    def parse_not(self):
        lineno = self.token_stream.lineno
        if self.token_stream.current.test('name:not'):
            next(self.token_stream)
            nodes.Not(self.parse_not(), lineno=lineno)
        return self.parse_compare()
    
    def parse_compare(self):
        lineno = self.token_stream.lineno
        expr = self.parse_math1()
        operands = []
        while True:
            token_type = self.token_stream.current.type
            if token_type in _compare_operators:
                next(self.token_stream)
                operands.append(nodes.Operand(token_type, self.parse_math1()))
            elif self.token_stream.skip_if('name:in'):
                operands.append(nodes.Operand('in', self.parse_math1()))
            elif self.token_stream.skip_if('name:not'):
                self.token_stream.expect('name:in')
                operands.append(nodes.Operand('notin', self.parse_math1()))
            else:
                break
        if not operands:
            return expr
        return nodes.Compare(expr, operands, lineno=lineno)

    def parse_math1(self):
        lineno = self.token_stream.lineno
        left = self.parse_math2()
        while self.token_stream.current.type in (tokens.ADD, tokens.SUB):
            cls = _math_nodes[next(self.token_stream).type]
            right = self.parse_math2()
            left = cls(left, right, lineno=lineno)
            lineno = self.token_stream.lineno
        return left

    def parse_math2(self):
        lineno = self.token_stream.lineno
        left = self.parse_pow()
        while self.token_stream.current.type in (tokens.MUL, tokens.DIV, 
            tokens.FLOOR_DIV, tokens.MOD):
            cls = _math_nodes[next(self.token_stream).type]
            right = self.parse_pow()
            left = cls(left, right, lineno=lineno)
            lineno = self.token_stream.lineno
        return left
    
    def parse_pow(self):
        lineno = self.token_stream.lineno
        left = self.parse_unary()
        while self.token_stream.current.type is tokens.POW:
            next(self.token_stream)
            right = self.parse_unary()
            left = nodes.Pow(left, right, lineno)
            lineno = self.token_stream.lineno
        return left

    def parse_unary(self):
        lineno = self.token_stream.lineno
        token_type = self.token_stream.current.type
        if token_type is tokens.ADD:
            next(self.token_stream)
            node = nodes.Pos(self.parse_unary(), lineno=lineno)
        elif token_type is tokens.SUB:
            next(self.token_stream)
            node = nodes.Neg(self.parse_unary(), lineno=lineno)
        else:
            node = self.parse_primary()
        node = self.parse_postfix(node)
        return node

    def parse_primary(self):
        token = self.token_stream.current
        lineno = token.lineno
        if token.value in ('True', 'False'):
            next(self.token_stream)
            return nodes.Const(token.value in ('True', 'False'), 
                            lineno=lineno)
        elif token.type is tokens.INTEGER:
            next(self.token_stream)
            return nodes.Const(int(token.value), lineno=lineno)
        elif token.type is tokens.FLOAT:
            next(self.token_stream)
            return nodes.Const(float(token.value), lineno=lineno)
        elif token.type is tokens.STRING:
            buffer = [next(self.token_stream).value]
            while self.token_stream.current.type is tokens.STRING:
                buffer.append(next(self.token_stream).value)
            return nodes.Const(concat(buffer), lineno=lineno)
        elif token.type is tokens.NAME:
            next(self.token_stream)
            return nodes.Name(token.value, 'load', lineno=lineno)
        elif token.type is tokens.LPAREN:
            next(self.token_stream)
            node = self.parse_tuple(explicit_parens=True)
            self.token_stream.expect(tokens.RPAREN)
        elif token.type is tokens.LBRACKET:
            node = self.parse_list()
        elif token.type is tokens.LBRACE:
            node = self.parse_dict()
        else:
            self.fail('unexpected character %r' % token.value, lineno)
        return node

    def parse_tuple(self, simplified=False, extra_end_rules=None, explicit_parens=False):
        items = []
        lineno = self.token_stream.lineno
        is_tuple = False

        parse = self.parse_expression
        if simplified:
            parse = self.parse_primary

        while True:
            if self.is_tuple_end(extra_end_rules):
                break
            if items:
                self.token_stream.expect(tokens.COMMA)
            items.append(parse())
            if self.token_stream.current.test(tokens.COMMA):
                is_tuple = True
            else:
                break

        if not is_tuple:
            if items:
                return items[0]

            if not explicit_parens:
                self.fail('expected expression for %s' % self.token_stream.current.value,
                        self.token_stream.lineno)

        return nodes.Tuple(items, 'load', lineno=lineno)

    def parse_list(self):
        lineno = self.token_stream.expect(tokens.LBRACKET).lineno
        items = []
        
        while self.token_stream.current.type is not tokens.RBRACKET:
            if items:
                self.token_stream.expect(tokens.COMMA)
            if self.token_stream.current.type is tokens.RBRACKET:
                break
            items.append(self.parse_expression())
        self.token_stream.expect(tokens.RBRACKET)
        return nodes.List(items, lineno=lineno)

    def parse_dict(self):
        lineno = self.token_stream.expect(tokens.RBRACE).lineno
        items = []

        while self.token_stream.current.type is not tokens.RBRACE:
            if items:
                self.token_stream.expect(tokens.COMMA)
            if self.token_stream.current.type is tokens.RBRACE:
                break
            token = self.token_stream.current
            key = self.parse_expression()
            self.token_stream.expect(tokens.COLON)
            value = self.parse_expression()
            items.append(nodes.Pair(key, value, lineno=token.lineno))
        self.token_stream.expect(tokens.RBRACE)
        return nodes.Dict(items, lineno=lineno)

    def parse_postfix(self, node):
        while True:
            token_type = self.token_stream.current.type
            if token_type is tokens.LPAREN:
                node = self.parse_call(node)
            elif token_type in (tokens.LBRACKET, tokens.DOT):
                node = self.parse_subscript(node)
            else:
                break
        return node

    def parse_call(self, node):
        lineno = self.token_stream.expect(tokens.LPAREN).lineno
        args = []
        kwargs = []
        dyn_args = dyn_kwargs = None
        require_comma = False

        def ensure(test):
            if not test:
                self.fail('unexpected call arguments', self.token_stream.lineno)

        while self.token_stream.current.type is not tokens.RPAREN:
            if require_comma:
                self.token_stream.expect(tokens.COMMA)    
                if self.token_stream.current.type is tokens.RPAREN:
                    break
            token = self.token_stream.current
            if token.type is tokens.MUL:
                ensure(dyn_args is None and dyn_kwargs is None)
                next(self.token_stream)
                dyn_args = self.parse_expression()
            elif token.type is tokens.POW:
                ensure(dyn_kwargs is None)
                next(self.token_stream)
                dyn_kwargs = self.parse_expression()
            else:
                ensure(dyn_args is None and dyn_kwargs is None)
                if (token.type is tokens.NAME and 
                    self.token_stream.look().type is tokens.ASSIGN):
                    key = next(self.token_stream).value
                    next(self.token_stream)
                    value = self.parse_expression()
                    kwargs.append(nodes.Keyword(key, value, 
                                lineno=token.lineno))
                else:
                    ensure(not kwargs)
                    args = self.parse_expression()
            require_comma = True
        self.token_stream.expect(tokens.RPAREN)
        return nodes.Call(node, args, kwargs, dyn_args, dyn_kwargs, 
                        lineno=lineno)

    def parse_subscript(self, node):
        token = next(self.token_stream)
        if token.type is tokens.DOT:
            attr_token = next(self.token_stream)
            if attr_token.type is tokens.NAME:
                return nodes.Getattr(node, attr_token.value, 'load', 
                                    lineno=token.lineno)
            self.fail('expected name instead of %r' % token.value, 
                    lineno=token.lineno)
        elif token.type is tokens.LBRACKET:
            node = nodes.Getitem(node, self.parse_subscribed(), 'load',
                                lineno=token.lineno)
            self.token_stream.expect(tokens.RBRACKET)
            return node
        self.fail('expected subscript character', lineno=token.lineno)

    def parse_subscribed(self):
        args = []
        expect_arg = True
        lineno = self.token_stream.current.lineno

        while self.token_stream.current.type is not tokens.RBRACKET:
            token = next(self.token_stream)
            if token.type is tokens.COLON:
                # we were expecting an argument
                # append None for empty arguments e.g [:10]
                if expect_arg:
                    args.append(None)
                # if we're at the end, the last argument is None
                # e.g [10:]
                if self.token_stream.current is tokens.RBRACKET:
                    args.append(None)
                expect_arg = True
                continue
            else:
                args.append(self.parse_expression())
                expect_arg = False
        
        if not args:
            self.fail('empty subscript', lineno=lineno)
        elif len(args) == 1:
            return args[0]
        return nodes.Slice(*args, lineno=lineno)

    def subparse(self, end_tokens=None):
        body = []
        buffer = []
        add_data = buffer.append

        def flush_data():
            if not buffer:
                return
            body.append(nodes.Output(buffer[:]))
            buffer.clear()

        def test_end_tokens(token):
            if end_tokens:
                return any(map(token.test, end_tokens))

        while not self.token_stream.closed:
            token = self.token_stream.current
            if token.type == tokens.DATA:
                add_data(nodes.TemplateData(token.value, lineno=token.lineno))
                next(self.token_stream)
            elif token.type == tokens.VARIABLE_BEGIN:
                next(self.token_stream)
                add_data(self.parse_tuple())
                self.token_stream.expect(tokens.VARIABLE_END)
            elif token.type == tokens.BLOCK_BEGIN:
                flush_data()
                next(self.token_stream)
                if test_end_tokens(self.token_stream.current):
                    return body
                rv = self.parse_statement()
                if isinstance(rv, list):
                    body.extend(rv)
                else:
                    body.append(rv)
                self.token_stream.expect(tokens.BLOCK_END)
            else:
                raise AssertionError('unexpected token %r in line %r' % (token.value, token.lineno))
            flush_data()

        return body

    def parse(self):
        return nodes.Template(self.subparse(), lineno=1)