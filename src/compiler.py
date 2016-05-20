import clang.cindex
import datamodel
import os
import types
import ast

EMPTY_DICT = dict()

def config_clang():
    prj_dir = os.path.dirname(os.path.dirname(__file__))
    libclang_dir = os.path.join(prj_dir, r'libclang\build\Release\bin')
    clang.cindex.Config.set_library_path(libclang_dir)

def astconv_expr(expr_cast):
    if expr_cast.kind.name == 'INTEGER_LITERAL':
        int_tok_cast = expr_cast.get_tokens().next()
        return ast.Num(n=int(int_tok_cast.spelling))
    elif expr_cast.kind.name == 'UNEXPOSED_EXPR':
        [val_ref_cast] = expr_cast.get_children()
        assert val_ref_cast.kind.name == 'DECL_REF_EXPR'
        return ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=val_ref_cast.spelling,
                ctx=ast.Load()),
            attr='val',
            ctx=ast.Load())
    else:
        raise AssertionError()

def astconv_var_decl(var_decl_cast):
    init_val_list = list(var_decl_cast.get_children())
    if len(init_val_list) == 1:
        args = [astconv_expr(init_val_list[0])]
    else:
        args = []
    return ast.Assign(
        targets=[ast.Name(id=var_decl_cast.spelling, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='datamodel', ctx=ast.Load()),
                attr='CInt', ctx=ast.Load()),
            args=args,
            keywords=[],
            starargs=None,
            kwargs=None))

def astconv_stmt(stmt_cast):
    assert stmt_cast.kind.name == 'BINARY_OPERATOR'
    assert stmt_cast.operator_kind.name == 'ASSIGN'
    decl_ref_cast, val_cast = stmt_cast.get_children()
    assert decl_ref_cast.kind.name == 'DECL_REF_EXPR'
    var_pyast = ast.Attribute(
        value=ast.Attribute(
            value=ast.Name(id='self', ctx=ast.Load()),
            attr=decl_ref_cast.spelling,
            ctx=ast.Load()),
        attr='val',
        ctx=ast.Store())
    return ast.Assign(
        targets=[var_pyast],
        value=astconv_expr(val_cast))

def astconv_func_decl(func_decl_cast):
    comp_stmt_cast, = func_decl_cast.get_children()
    assert comp_stmt_cast.kind.name == 'COMPOUND_STMT'
    stmts_pyast = [astconv_stmt(stmt_cast)
                   for stmt_cast in comp_stmt_cast.get_children()]
    return ast.FunctionDef(
        name=func_decl_cast.spelling,
        decorator_list=[],
        args=ast.arguments(args=[ast.Name(id='self', ctx=ast.Param())],
                           vararg=None,
                           kwarg=None,
                           defaults=[]),
        body=stmts_pyast or [ast.Pass()])

def astconv_decl(decl_cast):
    if decl_cast.kind.name == 'VAR_DECL':
        return astconv_var_decl(decl_cast)
    elif decl_cast.kind.name == 'FUNCTION_DECL':
        return astconv_func_decl(decl_cast)

def astconv_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    members_pyast = [astconv_decl(decl_cast)
                     for decl_cast in transunit.cursor.get_children()]
    ###classname has to be dereived from transunit's name
    class_def_pyast = ast.ClassDef(
        name='TransUnitCls',
        decorator_list=[],
        bases=[ast.Attribute(
            value=ast.Name(id='datamodel', ctx=ast.Load()),
            attr='CProgram', ctx=ast.Load())],
        body=members_pyast)
    module_pyast = ast.Module(body=[
        ast.Import(names=[ast.alias(name='datamodel', asname=None)]),
        class_def_pyast])   ###test empty classes
    ###transunit has to be derive from transunits name
    return module_pyast

def compile_transunit(transunit):
    module_pyast = astconv_transunit(transunit)
    ast.fix_missing_locations(module_pyast)
    module_pyc = compile(module_pyast, 'transunit_filename.c', 'exec')
    module = dict()
    exec module_pyc in module
    return module['TransUnitCls']


config_clang()