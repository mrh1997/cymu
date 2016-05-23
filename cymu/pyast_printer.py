import ast

def print_ast(node, include_attributes=False):
    """
    Prints a formatted dump of the tree in *node*.
    Derived from ast.dump, but extended provides a more clean presentation by
    adding new lines and indents
    """
    def is_complex_field(x):
        return (isinstance(x, ast.AST) and len(x._fields) > 0) or \
               isinstance(x, list)
    def _format(node, indent=0):
        indent_str = '\n'+'    '*(indent+1)
        if isinstance(node, ast.AST):
            fields = [(a, _format(b, indent+1)) for a, b in ast.iter_fields(node)]
            if not any(is_complex_field(b) for a, b in ast.iter_fields(node)):
                indent_str = ''
            rv = '%s(%s' % (node.__class__.__name__, ', '.join(
                ('%s%s=%s' % ((indent_str,)+field)
                 for field in fields)
            ))
            if include_attributes and node._attributes:
                rv += fields and ', ' or ' '
                rv += ', '.join('%s%s=%s' % (indent_str, a, _format(getattr(node, a), indent+1))
                                for a in node._attributes)
            return rv + ')'
        elif isinstance(node, list):
            if len(node) == 0:
                indent_str = ''
            return '[%s]' % ', '.join(indent_str + _format(x, indent+1) for x in node)
        return repr(node)
    if not isinstance(node, ast.AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    print _format(node)
