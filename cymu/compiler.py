import clang.cindex
import os
import ast
import functools

EMPTY_DICT = dict()

class CompileError(Exception):
    pass

def with_src_location():
    """
    This decorator for ast-converters adds the source location of the passed
    c-ast to the returned python-ast.

    :param f(int) astconv_func: the function that shall be decorated
    """
    def decorator(astconv_func):
        @functools.wraps(astconv_func)
        def astconv_wrapper(cast):
            pyast = astconv_func(cast)
            pyast.lineno = cast.location.line
            pyast.col_offset = cast.location.column-1
            return pyast
        return astconv_wrapper
    return decorator

def config_clang():
    prj_dir = os.path.dirname(os.path.dirname(__file__))
    libclang_dir = os.path.join(prj_dir, r'libclang\build\Release\bin')
    clang.cindex.Config.set_library_path(libclang_dir)

@with_src_location()
def astconv_expr(expr_astc):
    if expr_astc.kind.name == 'INTEGER_LITERAL':
        int_tok_astc = expr_astc.get_tokens().next()
        return ast.Num(n=int(int_tok_astc.spelling))
    elif expr_astc.kind.name == 'UNEXPOSED_EXPR':
        [val_ref_astc] = expr_astc.get_children()
        assert val_ref_astc.kind.name == 'DECL_REF_EXPR'
        return ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=val_ref_astc.spelling,
                ctx=ast.Load()),
            attr='val',   ### remove '.val' (use reference to CObject instead). CObjects have to be extended to support all python special methods for this...
            ctx=ast.Load())
    else:
        raise AssertionError('Unsupportet Expression {!r}'
                             .format(expr_astc.kind.name))

def astconv_var_decl(var_decl_astc):
    init_val_list = list(var_decl_astc.get_children())
    if len(init_val_list) == 1:
        args = [astconv_expr(init_val_list[0])]
    else:
        args = []
    return ast.Assign(
        targets=[ast.Name(id=var_decl_astc.spelling, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='datamodel', ctx=ast.Load()),
                attr='CInt', ctx=ast.Load()),
            args=args,
            keywords=[],
            starargs=None,
            kwargs=None))

@with_src_location()
def astconv_stmt(stmt_astc):
    children = list(stmt_astc.get_children())
    if stmt_astc.kind.name in ('BINARY_OPERATOR', 'COMPOUND_ASSIGNMENT_OPERATOR'):
        decl_ref_astc, val_astc = children
        assert decl_ref_astc.kind.name == 'DECL_REF_EXPR'
        var_astpy = ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=decl_ref_astc.spelling,
                ctx=ast.Load()),
            attr='val',
            ctx=ast.Store())
        if stmt_astc.kind.name == 'BINARY_OPERATOR':
            assert stmt_astc.operator_kind.name == 'ASSIGN'
            return ast.Assign(
                targets=[var_astpy],
                value=astconv_expr(val_astc))
        else:
            assert stmt_astc.operator_kind.name == 'SUB_ASSIGN'
            return ast.AugAssign(
                target=var_astpy,
                op=ast.Sub(),
                value=astconv_expr(val_astc))
    elif stmt_astc.kind.name == 'IF_STMT':
        return ast.If(
            test=astconv_expr(children[0]),
            body=astconv_stmt_list(children[1]),
            orelse=([] if len(children) != 3
                    else astconv_stmt_list(children[2])))
    elif stmt_astc.kind.name == 'NULL_STMT':
        return ast.Pass()
    elif stmt_astc.kind.name == 'WHILE_STMT':
        return ast.While(test=astconv_expr(children[0]),
                         body=astconv_stmt_list(children[1]),
                         orelse=[])
    elif stmt_astc.kind.name == 'DO_STMT':
        return ast.While(
            test=ast.Name(id='True', ctx=ast.Load()),
            body=astconv_stmt_list(children[0]) + [
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=astconv_expr(children[1])),
                    body=[ast.Break()],
                    orelse=[])],
            orelse=[])
    else:
        raise AssertionError('Unsupportet Statement {!r}'
                             .format(stmt_astc.kind.name))

def astconv_stmt_list(body_astc):
    if body_astc.kind.name == 'COMPOUND_STMT':
        def flatten_compound_stmts(compound_stmt_astc):
            for stmt_astc in compound_stmt_astc.get_children():
                if stmt_astc.kind.name == 'COMPOUND_STMT':
                    flatten_compound_stmts(stmt_astc)
                else:
                    body_astpy_list.append(astconv_stmt(stmt_astc))
        body_astpy_list = []
        flatten_compound_stmts(body_astc)
        if len(body_astpy_list) == 0:
            body_astpy_list.append(ast.Pass())
        return body_astpy_list
    else:
        return [astconv_stmt(body_astc)]

def astconv_func_decl(func_decl_astc):
    children = list(func_decl_astc.get_children())
    if len(children) == 1:
        return ast.FunctionDef(
            name=func_decl_astc.spelling,
            decorator_list=[],
            args=ast.arguments(args=[ast.Name(id='self', ctx=ast.Param())],
                               vararg=None,
                               kwarg=None,
                               defaults=[]),
            body=astconv_stmt_list(children[0]))
    else:
        return ast.Pass()

@with_src_location()
def astconv_decl(decl_astc):
    if decl_astc.kind.name == 'VAR_DECL':
        return astconv_var_decl(decl_astc)
    elif decl_astc.kind.name == 'FUNCTION_DECL':
        return astconv_func_decl(decl_astc)

def astconv_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    members_astpy = [astconv_decl(decl_astc)
                     for decl_astc in transunit.cursor.get_children()]
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