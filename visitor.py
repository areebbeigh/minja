class NodeVisitor:
    def get_visitor(self, node):
        method = getattr(self, 'visit_' + node.__class__.__name__, None)
        # assert method, 'no visitor found for node %r' % node
        return method

    def visit(self, node, *args, **kwargs):
        visitor = self.get_visitor(node)
        if visitor is not None:
            return visitor(node, *args, **kwargs)
        return self.generic_visitor(node, *args, **kwargs)

    def generic_visitor(self, node, *args, **kwargs):
        for node in node.iter_child_nodes():
            self.visit(node, *args, **kwargs)