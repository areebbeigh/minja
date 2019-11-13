import nodes
from nodes import EvalContext
from idtracking import (Symbols, VAR_LOAD_PARAM, VAR_LOAD_RESOLVE, 
                        VAR_LOAD_STORE, VAR_LOAD_UNDEFINED)
from visitor import NodeVisitor
from utils import escape
from io import StringIO

operators = {
    'eq':       '==',
    'ne':       '!=',
    'gt':       '>',
    'gteq':     '>=',
    'lt':       '<',
    'lteq':     '<=',
    'in':       'in',
    'notin':    'not in'
}

def generate(node, environment, name, stream=None):
    if not isinstance(node, nodes.Template):
        raise TypeError('Can\'t compile non-template nodes')
    generator = CodeGenerator(environment, name, stream)
    generator.visit(node)
    if stream is None:
        return generator.stream.getvalue()

def find_undeclared(nodes, names):
    visitor = UndeclaredNameVisitor(names)
    for node in nodes:
        try:
            visitor.visit(node)
        except VisitorExit: 
            pass
    return visitor.undeclared

class VisitorExit(RuntimeError): pass


class UndeclaredNameVisitor(NodeVisitor):
    def __init__(self, names):
        self.names = set(names)
        self.undeclared = set()
    
    def visit_Name(self, node):
        if node.ctx == 'load' and node.name in self.names:
            self.undeclared.add(node.name)
            if self.undeclared == self.names:
                raise VisitorExit()
        else:
            self.names.discard(node.name)


class Frame:
    def __init__(self, eval_ctx, parent=None, level=None):
        self.eval_ctx = eval_ctx
        self.parent = parent
        self.symbols = Symbols(parent and parent.symbols or None, level)
    
    def inner(self, isolated=False):
        if isolated:
            return Frame(self.eval_ctx, level=self.symbols.level + 1)
        return Frame(self.eval_ctx, self)


class CodeGenerator(NodeVisitor):
    def __init__(self, environment, name, stream):
        if stream is None:
            stream = StringIO()
        self.environment = environment
        self.stream = stream
        self.code_lineno = 1
        self.blocks = {}
        self.name = name
        self._first_write = True
        self._new_lines = self._indentation = 0
        self._last_identifier = 0
        

    def fail(self, msg, lineno, name):
        assert False, msg + str(lineno) + name

    def temporary_identifier(self):
        self._last_identifier += 1
        return 't_%s' % self._last_identifier

    def write(self, x):
        if self._new_lines:
            if not self._first_write:
                self.stream.write('\n' * self._new_lines)
                self.code_lineno += self._new_lines
            self._first_write = False
            self.stream.write('    ' * self._indentation)
            self._new_lines = 0
        self.stream.write(x)

    def writeline(self, x, node=None, extra=0):
        self.newline(node, extra)
        self.write(x)

    def newline(self, node=None, extra=0):
        self._new_lines = max(self._new_lines, extra + 1)
        if node is not None:
            self._last_line = node.lineno

    def indent(self):
        self._indentation += 1

    def outdent(self, step=1):
        self._indentation -= step

    def enter_frame(self, frame):
        undefs = set()
        for ident, (action, param) in frame.symbols.loads.items():
            # print('enter:', ident, action, param)
            if action == VAR_LOAD_PARAM:
                pass
            elif action == VAR_LOAD_RESOLVE:
                self.writeline('%s = %s(%r)' % 
                    (ident, self.get_resolve_func(), param))
            elif action == VAR_LOAD_UNDEFINED:
                undefs.add(ident)
            else:
                raise NotImplementedError('unknown load instruction')
        if undefs:
            self.writeline('%s = missing' % ' = '.join(undefs))

    def leave_frame(self, frame, keep_scope=False):
        if not keep_scope:
            undefs = set()
            for ident, _ in frame.symbols.loads.items():
                undefs.add(ident)
            if undefs:
                self.writeline('%s = missing' % ' = '.join(undefs))

    def func(self, name):
        return 'def {}'.format(name)

    def get_resolve_func(self):
        return 'resolve'

    def blockvisit(self, nodes, frame):
        self.writeline('pass')
        for node in nodes:
            self.visit(node, frame)

    def write_commons(self):
        self.writeline('resolve = context.resolve_or_missing')
        self.writeline('undefined = evironment.undefined')
        self.writeline('if 0: yield None')

    def signature(self, node, frame):
        for arg in node.args:
            self.write(', ')
            self.visit(arg, frame)
        for kwarg in node.kwargs:
            self.write(', ')
            self.visit(kwarg, frame)
        if node.dyn_args:
            self.write(', *')
            self.visit(node.dyn_args, frame)
        if node.dyn_kwargs:
            self.write(', **')
            self.visit(node.dyn_kwargs, frame)

    def visit_Template(self, node, frame=None):
        assert frame is None, 'no root frame allowed'
        eval_ctx = EvalContext(self.environment, self.name)
        # TODO: Write runtime imports

        for block in node.find_all(nodes.Block):
            if block.name in self.blocks:
                self.fail('block %r defined twice' % 
                        block.name, block.lineno, self.name)
            self.blocks[block.name] = block

        self.writeline('name = %r' % self.name)

        # write root render function for this template
        self.writeline('%s(context, missing=missing, environment=environment):' %
                        (self.func('root')), extra=1)
        self.indent()
        self.write_commons()

        frame = Frame(eval_ctx)
        frame.symbols.analyze_node(node)
        # frame.toplever = frame.rootlevel = True
        # TODO: resolve extends output checks
        self.enter_frame(frame)
        self.blockvisit(node.body, frame)
        self.leave_frame(frame, keep_scope=True)
        self.outdent()

        # TODO: yield from parent templates if have_extends
        # visit blocks
        for name, block in self.blocks.items():
            self.writeline('%s(context, missing=missing, environment=environment):' %
                            (self.func('block_' + name)), block, 1)
            self.indent()
            self.write_commons()
            block_frame = Frame(eval_ctx)
            block_frame.symbols.analyze_node(block)
            block_frame.block = name
            self.enter_frame(block_frame)
            self.blockvisit(block.body, block_frame)
            self.leave_frame(block_frame, keep_scope=True)
            self.outdent()

        self.writeline('blocks = {%s}' % ', '.join('%r: block_%s' % (x, x)
                        for x in self.blocks), extra=1)
    
    def visit_Block(self, node, frame):
        self.writeline('yield from context.blocks[%r][0](%s)' % (
                        node.name, 'context'))
    
    def visit_For(self, node, frame):
        # print('visit_For:', frame.symbols.loads)
        loop_frame = frame.inner()
        test_frame = frame.inner()
        else_frame = frame.inner()

        loop_frame.symbols.analyze_node(node, for_branch='body')
        if node.else_:
            else_frame.symbols.analyze_node(node, for_branch='else')
        if node.test:
            loop_filter_func = self.temporary_identifier()
            test_frame.symbols.analyze_node(node, for_branch='test')
            self.writeline('%s(fiter):' % self.func(loop_filter_func))
            self.indent()
            self.enter_frame(test_frame)
            self.writeline('for ')
            self.visit(node.target, loop_frame)
            self.write(' in fiter:')
            self.indent()
            self.writeline('if ')
            self.visit(node.test)
            self.write(':')
            self.indent()
            self.writeline('yield ')
            self.visit(node.target, loop_frame)
            self.outdent(3)
            self.leave_frame(test_frame, keep_scope=True)
        
        if node.else_:
            iter_indicator = self.temporary_identifier()
            self.writeline('%s = 1' % iter_indicator)

        self.writeline('for ')
        self.visit(node.target, loop_frame)
        self.write(' in ')
        if node.test:
            self.write('%s(' % loop_filter_func)
        self.visit(node.iter, frame)
        if node.test:
            self.write(')')
        self.write(':')
        self.indent()
        self.enter_frame(loop_frame)
        self.blockvisit(node.body, loop_frame)
        self.writeline('%s = 0' % iter_indicator)
        self.outdent()
        self.leave_frame(loop_frame, not node.else_)
        
        if node.else_:
            self.writeline('if %s:' % iter_indicator)
            self.indent()
            self.enter_frame(else_frame)
            self.blockvisit(node.else_, else_frame)
            self.leave_frame(else_frame)
            self.outdent()

    def visit_If(self, node, frame):
        if_frame = frame.soft()
        self.writeline('if ', node)
        self.visit(node.body, if_frame)
        self.write(':')
        self.indent()
        self.blockvisit(node.body, if_frame)
        self.outdent()
        for elif_ in node.elif_:
            self.writeline('elif ', elif_)
            self.visit(elif_.test, if_frame)
            self.write(':')
            self.indent()
            self.blockvisit(elif_.body, if_frame)
            self.outdent()
        if node.else_:
            self.writeline('else:')
            self.indent()
            self.blockvisit(node.else_, if_frame)
            self.outdent()

    def visit_With(self, node, frame):
        with_frame = frame.inner()
        with_frame.symbols.analyze_node(node)
        self.enter_frame(with_frame)
        for target, expr in zip(node.targets, node.values):
            self.newline()
            self.visit(target, with_frame)
            self.write(' = ')
            self.visit(expr, frame)
        self.blockvisit(node.body, with_frame)
        self.leave_frame(with_frame)

    def visit_Output(self, node, frame):
        body = []
        for child in node.nodes:
            try:
                const = child.as_const(frame.eval_ctx)
            except nodes.Impossible:
                body.append(child)
                continue
            
            try:
                if frame.eval_ctx.autoescape:
                    if hasattr(const, '__html__'):
                        const = const.__html__()
                    else:
                        const = escape(const)
                const = str(const)
            except Exception:
                body.append(child)
                continue
            
            if body and isinstance(body[-1], list):
                body[-1].append(const)
            else:
                body.append([const])
        # write a format string for the body
        format = []
        arguments = []
        for item in body:
            if isinstance(item, list):
                format.append(u''.join(item).replace('%', '%%'))
            else:
                format.append('%s')
                arguments.append(item)
        self.writeline('yield ')
        self.write(repr(u''.join(format)))
        if arguments:
            self.write(' % (')
            self.indent()
            for argument in arguments:
                self.newline(argument)
                close = 0
                if frame.eval_ctx.autoescape:
                    self.write('escape(')
                    close += 1
                self.visit(argument, frame)
                self.write(')' * close)
            self.outdent()
            self.writeline(')')

    def visit_Name(self, node, frame):
        # print('visiting', node)
        # print(frame.symbols.loads)
        ref = frame.symbols.ref(node.name)
        if node.ctx == 'load':
            load = frame.symbols.find_load(ref)
            if not (load is not None and load[0] == VAR_LOAD_PARAM):
                self.write('(undefined(name=%r) if %s is missing else %s)' % 
                        (node.name, ref, ref))
                return
        self.write(ref)

    def visit_Const(self, node, frame):
        val = node.as_const(frame.eval_ctx)
        if isinstance(val, float):
            self.write(str(val))
        else:
            self.write(repr(val))

    def visit_TemplateData(self, node, frame):
        try:
            self.write(repr(node.as_const(frame.eval_ctx)))
        except nodes.Impossible:
            self.write('(Markup if context.eval_ctx.autoescape else identity)(%r)'
                        % node.data)

    def visit_Tuple(self, node, frame):
        self.write('(')
        idx = -1
        for idx, item in enumerate(node.items):
            if idx:
                self.write(',')
            self.visit(item, frame)
        self.write(idx == 0 and ',' or ')')

    def visit_List(self, node, frame):
        self.write('[')
        for idx, item in enumerate(node.items):
            if idx:
                self.write(',')
            self.visit(item, frame)
        self.write(']')

    def visit_Dict(self, node, frame):
        self.write('{')
        for idx, item in enumerate(node.items()):
            if idx:
                self.write(',')
            self.visit(item.key, frame)
            self.write(':')
            self.visit(item.value, frame)
        self.write('}')

    def binop(operator):
        def visitor(self, node, frame):
            self.write('(')
            self.visit(node.left)
            self.write(' %s ' % operator)
            self.visit(node.right)
            self.write(')')
        return visitor

    def unaop(operator):
        def visitor(self, node, frame):
            self.write('(' + operator)
            self.visit(node.node, frame)
            self.write(')')
        return visitor

    visit_Add = binop('+')
    visit_Sub = binop('-')
    visit_Mul = binop('*')
    visit_Div = binop('/')
    visit_FloorDiv = binop('//')
    visit_Pow = binop('**')
    visit_Mod = binop('%')
    visit_Or = binop('or')
    visit_And = binop('and')
    visit_Pos = unaop('+')
    visit_Neg = unaop('-')
    visit_Not = unaop('not')
    del binop, unaop

    def visit_Compare(self, node, frame):
        self.visit(node.expr)
        for op in node.operands:
            self.visit(op, frame)

    def visit_Operand(self, node, frame):
        self.write(' %s ' % operators[node.operator])
        self.visit(node.expr, frame)

    def visit_Getattr(self, node, frame):
        self.write('environment.getattr(')
        self.visit(node.node, frame)
        self.write(', %r' % node.attr)

    def visit_Getitem(self, node, frame):
        if isinstance(node.arg, nodes.Slice):
            self.visit(node.node, frame)
            self.write('[')
            self.visit(node.arg, frame)
            self.write(']')
        else:
            self.write('environment.getitem(')
            self.visit(node.node, frame)
            self.write(', ')
            self.visit(node.arg, frame)
            self.write(')')

    def visit_Slice(self, node, frame):
        if node.start is not None:
            self.visit(node.start, frame)
        self.write(':')
        if node.stop is not None:
            self.visit(node.stop, frame)
        if node.step is not None:
            self.write(':')
            self.visit(node.step, frame)

    def visit_Call(self, node, frame):
        self.write('context.call(')
        self.visit(node.node, frame)
        self.signature(node, frame)
        self.write(')')

    def visit_Keyword(self, node, frame):
        self.write(node.key + '=')
        self.visit(node.value, frame)