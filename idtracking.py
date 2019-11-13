from visitor import NodeVisitor

VAR_LOAD_RESOLVE = 'resolve'
VAR_LOAD_PARAM = 'param'
VAR_LOAD_STORE = 'store'
VAR_LOAD_ALIAS = 'alias'
VAR_LOAD_UNDEFINED = 'undefined'

class Symbols:
    def __init__(self, parent=None, level=None):
        if level is None:
            if parent is not None:
                level = parent.level + 1
            else:
                level = 0
        self.parent = parent
        self.level = level
        self.refs = {}
        self.loads = {}
        self.stores = set()
    
    def analyze_node(self, node, **kwargs):
        visitor = RootVisitor(self)
        visitor.visit(node, **kwargs)

    def find_ref(self, name):
        if name in self.refs:
            return self.refs[name]
        if self.parent is not None:
            return self.parent.find_ref(name)

    def find_load(self, target):
        if target in self.loads:
            return self.loads[target]
        if self.parent is not None:
            return self.parent.find_load(target)

    def _define_ref(self, name, load=None):
        ident = 'l_%s_%s' % (self.level, name)
        self.refs[name] = ident
        if load is not None:
            self.loads[ident] = load
        return ident

    def load(self, name):
        target = self.find_ref(name)
        if not target:
            self._define_ref(name, load=(VAR_LOAD_RESOLVE, name))

    def ref(self, name):
        rv = self.find_ref(name)
        assert rv is not None, ('Tried to resolve a name to a reference that' 
                                'was unknown to the frame (%r)' % name)
        return rv

    def declare_parameter(self, name):
        self.stores.add(name)
        self._define_ref(name, load=(VAR_LOAD_PARAM, None))

    def store(self, name):
        pass

    def branch_update(self):
        pass


class RootVisitor(NodeVisitor):
    def __init__(self, symbols):
        self.sym_visitor = FrameSymbolVisitor(symbols)

    def _generic_visit(self, node):
        for child in node.iter_child_nodes():
            self.sym_visitor.visit(child)

    visit_Template = visit_Block = visit_If = _generic_visit

    def visit_For(self, node, for_branch='body', **kwargs):
        if for_branch == 'body':
            self.sym_visitor.visit(node.target, store_as_param=True)
            branch = node.body
        elif for_branch == 'else':
            branch = node.else_
        elif for_branch == 'test':
            self.sym_visitor.visit(node.target, store_as_param=True)
            if node.test is not None:
                self.sym_visitor.visit(node.test)
            return
        else:
            raise RuntimeError('unknown for branch')
        
        for item in branch:
            self.sym_visitor.visit(item)

    def visit_With(self, node, **kwargs):
        for target in node.targets:
            self.sym_visitor.visit(target)
        for child in node.body:
            self.sym_visitor.visit(child)


class FrameSymbolVisitor(NodeVisitor):
    def __init__(self, symbols):
        self.symbols = symbols

    def visit_Name(self, node, store_as_param=False, **kwargs):
        if store_as_param or node.ctx == 'param':
            self.symbols.declare_parameter(node.name)
        elif node.ctx == 'load':
            self.symbols.load(node.name)

    def visit_If(self, node, **kwargs):
        self.visit(node.test, **kwargs)
        
        def inner_visit(nodes):
            for subnode in nodes:
                self.visit(subnode, **kwargs)
        
        tuple(map(inner_visit, (node.body, node.elif_, node.else_)))

    def visit_For(self, node, **kwargs):
        self.visit(node.iter, **kwargs)

    def visit_With(self, node):
        for target in node.values:
            self.visit(target)

    def visit_Block(self, node, **kwargs):
        """Visiting stops at blocks"""