import clang.cindex
import os
import ast
import functools

# this value is vor debugging purposes.
# It prints the python AST of compiled C-code
PRINT_PYAST = False

class CompileError(Exception):
    pass

def config_clang():
    prj_dir = os.path.dirname(os.path.dirname(__file__))
    libclang_dir = os.path.join(prj_dir, r'libclang\build\Release\bin')
    clang.cindex.Config.set_library_path(libclang_dir)


def with_src_location():
    """
    This decorator for ast-converters adds the source location of the passed
    c-ast to the returned python-ast.

    :param f(int) astconv_func: the function that shall be decorated
    """
    def decorator(astconv_func):
        @functools.wraps(astconv_func)
        def astconv_wrapper(astc, local_names, prefix_stmts):
            pyast = astconv_func(astc, local_names, prefix_stmts)
            pyast.lineno = astc.location.line
            pyast.col_offset = astc.location.column - 1
            return pyast
        return astconv_wrapper
    return decorator

def astconv_expr(expr_astc, local_names, prefix_stmts):
    children = list(expr_astc.get_children())
    if expr_astc.kind.name in ('BINARY_OPERATOR', 'COMPOUND_ASSIGNMENT_OPERATOR'):
        decl_ref_astc, val_astc = children
        assert decl_ref_astc.kind.name == 'DECL_REF_EXPR'
        if local_names is not None and decl_ref_astc.spelling in local_names:
            var_astpy = ast.Name(id=decl_ref_astc.spelling, ctx=ast.Load())
        else:
            var_astpy = ast.Attribute(
                value=ast.Name(id='__globals__', ctx=ast.Load()),
                attr=decl_ref_astc.spelling,
                ctx=ast.Load())
        val_astpy = ast.Attribute(value=var_astpy, attr='val', ctx=ast.Store())
        if expr_astc.kind.name == 'BINARY_OPERATOR':
            assert expr_astc.operator_kind.name == 'ASSIGN'
            prefix_stmts.append(ast.Assign(
                targets=[val_astpy],
                value=astconv_expr(val_astc, local_names, prefix_stmts)))
        else:
            assert expr_astc.operator_kind.name == 'SUB_ASSIGN'
            prefix_stmts.append(ast.AugAssign(
                target=val_astpy,
                op=ast.Sub(),
                value=astconv_expr(val_astc, local_names, prefix_stmts)))
        return var_astpy
    elif expr_astc.kind.name == 'INTEGER_LITERAL':
        int_tok_astc = expr_astc.get_tokens().next()
        int_astpy = ast.Num(n=int(int_tok_astc.spelling))
        if local_names is None:  # global variable definition?
            type_container = ast.Attribute(
                value=ast.Name(id='datamodel', ctx=ast.Load()),
                attr='CProgram', ctx=ast.Load())
        else:
            type_container = ast.Name(id='__globals__', ctx=ast.Load())
        return ast.Call(
            func=ast.Attribute(
                value=type_container,
                attr='int',
                ctx=ast.Load()),
            args=[int_astpy],
            keywords=[],
            starargs=None,
            kwargs=None)
    elif expr_astc.kind.name == 'UNEXPOSED_EXPR':
        [val_ref_astc] = children
        assert val_ref_astc.kind.name == 'DECL_REF_EXPR'
        if local_names is not None and val_ref_astc.spelling in local_names:
            obj_ref_astpy = ast.Name(id=val_ref_astc.spelling, ctx=ast.Load())
        else:
            obj_ref_astpy = ast.Attribute(
                value=ast.Name(id='__globals__', ctx=ast.Load()),
                attr=val_ref_astc.spelling,
                ctx=ast.Load())
        return ast.Attribute(
            value=obj_ref_astpy,
            attr='val',
            ctx=ast.Load())
    else:
        raise AssertionError('Unsupportet Expression {!r}'
                             .format(expr_astc.kind.name))

@with_src_location()
def astconv_var_decl(var_decl_astc, local_names, prefix_stmts):
    init_val_list = list(var_decl_astc.get_children())
    if len(init_val_list) == 1:
        args = [astconv_expr(init_val_list[0], local_names, prefix_stmts)]
    else:
        args = []
    if local_names is None:   # global variable definition?
        type_container = ast.Attribute(
            value=ast.Name(id='datamodel', ctx=ast.Load()),
            attr='CProgram', ctx=ast.Load())
    else:
        local_names.add(var_decl_astc.spelling)
        type_container = ast.Name(id='__globals__', ctx=ast.Load())
    return ast.Assign(
        targets=[ast.Name(id=var_decl_astc.spelling, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Attribute(
                value=type_container,
                attr='int',
                ctx=ast.Load()),
            args=args,
            keywords=[],
            starargs=None,
            kwargs=None))

def astconv_compound_stmt(comp_stmt_astc, local_names, prefix_stmts):
    for stmt_astc in comp_stmt_astc.get_children():
        if stmt_astc.kind.name == 'DECL_STMT':
            [child] = stmt_astc.get_children()
            stmt_astpy = astconv_var_decl(child, local_names, prefix_stmts)
        else:
            stmt_astpy = astconv_stmt(stmt_astc, local_names, prefix_stmts)
        prefix_stmts.append(stmt_astpy)
    return ast.Pass()

@with_src_location()
def astconv_if_stmt(if_stmt_astc, local_names, prefix_stmts):
    children = list(if_stmt_astc.get_children())
    return ast.If(
        test=astconv_expr(children[0], local_names, prefix_stmts),
        body=to_stmt_list(children[1], local_names),
        orelse=([] if len(children) != 3
                else to_stmt_list(children[2], local_names)))

@with_src_location()
def astconv_while_stmt(while_stmt_astc, local_names, prefix_stmts):
    [exit_cond_astc, body_astc] = while_stmt_astc.get_children()
    exit_check_prefix_stmts = []
    exit_check_astpy = astconv_expr(exit_cond_astc, local_names,
                                    exit_check_prefix_stmts)
    astconv_expr(exit_cond_astc, local_names, prefix_stmts)
    return ast.While(
        test=exit_check_astpy,
        body=to_stmt_list(body_astc, local_names) + exit_check_prefix_stmts,
        orelse=[])

@with_src_location()
def astconv_dowhile_stmt(dowhile_stmt_astc, local_names, prefix_stmts):
    [body_astc, exit_cond_astc] = dowhile_stmt_astc.get_children()
    exit_check_prefix_stmts = []
    exit_check_astpy = ast.If(
        test=ast.UnaryOp(
            op=ast.Not(),
            operand=astconv_expr(exit_cond_astc, local_names,
                                 exit_check_prefix_stmts)),
        body=[ast.Break()],
        orelse=[])
    return ast.While(
        test=ast.Name(id='True', ctx=ast.Load()),
        body=to_stmt_list(body_astc, local_names) +
             exit_check_prefix_stmts + [exit_check_astpy],
        orelse=[])

@with_src_location()
def astconv_expr_as_stmt(stmt_astc, local_names, prefix_stmts):
    astconv_expr(stmt_astc, local_names, prefix_stmts)
    return ast.Pass()

def astconv_stmt(stmt_astc, local_names, prefix_stmts):
    if stmt_astc.kind.name == 'IF_STMT':
        return astconv_if_stmt(stmt_astc, local_names, prefix_stmts)
    elif stmt_astc.kind.name == 'NULL_STMT':
        return ast.Pass()
    elif stmt_astc.kind.name == 'WHILE_STMT':
        return astconv_while_stmt(stmt_astc, local_names, prefix_stmts)
    elif stmt_astc.kind.name == 'DO_STMT':
        return astconv_dowhile_stmt(stmt_astc, local_names, prefix_stmts)
    elif stmt_astc.kind.name == 'COMPOUND_STMT':
        return astconv_compound_stmt(stmt_astc, local_names, prefix_stmts)
    else:
        return astconv_expr_as_stmt(stmt_astc, local_names, prefix_stmts)

def to_stmt_list(stmt_astc, local_names):
    stmt_list = []
    stmt_astpy = astconv_stmt(stmt_astc, local_names, prefix_stmts=stmt_list)
    if not isinstance(stmt_astpy, ast.Pass) or \
            hasattr(stmt_astpy, 'lineno') or \
            len(stmt_list) == 0:
        stmt_list.append(stmt_astpy)

    # To ensure that debug-linenos are in ascending order (required by python)
    # the prefix statements (they do not have their own lineno) takeover the
    # location of the corresponding prefixed statement
    for next_astpy, prev_astpy in reversed(zip(stmt_list[1:], stmt_list[:-1])):
        if not hasattr(prev_astpy, 'lineno'):
            ast.copy_location(prev_astpy, next_astpy)

    return stmt_list

@with_src_location()
def astconv_func_decl(func_decl_astc, local_names, prefix_stmts):
    children = list(func_decl_astc.get_children())
    if len(children) == 1:
        return ast.FunctionDef(
            name=func_decl_astc.spelling,
            decorator_list=[],
            args=ast.arguments(args=[ast.Name(id='__globals__', ctx=ast.Param())],
                               vararg=None,
                               kwarg=None,
                               defaults=[]),
            body=to_stmt_list(children[0], local_names=set()))
    else:
        return ast.Pass()

def astconv_decl(decl_astc, local_names, prefix_stmts):
    if decl_astc.kind.name == 'VAR_DECL':
        return astconv_var_decl(decl_astc, local_names, prefix_stmts)
    elif decl_astc.kind.name == 'FUNCTION_DECL':
        return astconv_func_decl(decl_astc, local_names, prefix_stmts)

def astconv_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    prefix_stmts = []
    members_astpy = [astconv_decl(decl_astc, None, prefix_stmts)
                     for decl_astc in transunit.cursor.get_children()]
    assert len(prefix_stmts) == 0

    class_def_astpy = ast.ClassDef(
        name='CModule',
        decorator_list=[],
        bases=[ast.Attribute(
            value=ast.Name(id='datamodel', ctx=ast.Load()),
            attr='CProgram', ctx=ast.Load())],
        body=members_astpy)
    module_astpy = ast.Module(body=[
        ast.ImportFrom(module='cymu',
                       names=[ast.alias(name='datamodel', asname=None)]),
        class_def_astpy])
    return module_astpy

def compile_transunit(transunit):
    module_astpy = astconv_transunit(transunit)
    ast.fix_missing_locations(module_astpy)
    if PRINT_PYAST:
        import pyast_printer
        pyast_printer.print_ast(module_astpy, True)
    module_pyc = compile(module_astpy, transunit.spelling, 'exec')
    module = dict()
    exec module_pyc in module
    return module['CModule']

def compile_str(c_code, filename='filename.c'):
    index = clang.cindex.Index.create()
    transunit = index.parse(filename, unsaved_files=[(filename, c_code)])
    if len(list(transunit.diagnostics)) > 0:
        raise CompileError('invalid C-code')
    return compile_transunit(transunit)

def compile_file(c_filename):
    index = clang.cindex.Index.create()
    transunit = index.parse(c_filename)
    if len(list(transunit.diagnostics)) > 0:
        raise CompileError('invalid C-code')
    return compile_transunit(transunit)

config_clang()
