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

def parse_var_decl(var_decl_cast):
    init_val_list = list(var_decl_cast.get_children())
    if len(init_val_list) == 1:
        int_lit_cast = init_val_list[0]
        assert int_lit_cast.kind.name == 'INTEGER_LITERAL'
        int_tok_cast = int_lit_cast.get_tokens().next()
        args = [ast.Num(n=int(int_tok_cast.spelling))]
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

def parse_func_decl(func_decl_cast):
    comp_stmt_cast, = func_decl_cast.get_children()
    assert comp_stmt_cast.kind.name == 'COMPOUND_STMT'
    stmts_pyast = []
    for stmt_cast in comp_stmt_cast.get_children():
        assert stmt_cast.kind.name == 'BINARY_OPERATOR'
        assert stmt_cast.operator_kind.name == 'ASSIGN'
        decl_ref_cast, val_cast = stmt_cast.get_children()
        assert decl_ref_cast.kind.name == 'DECL_REF_EXPR'
        if val_cast.kind.name == 'INTEGER_LITERAL':
            int_tok_cast = val_cast.get_tokens().next()
            val = ast.Num(n=int(int_tok_cast.spelling))
        elif val_cast.kind.name == 'UNEXPOSED_EXPR':
            [val_ref_cast] = val_cast.get_children()
            assert val_ref_cast.kind.name == 'DECL_REF_EXPR'
            val = ast.Attribute(
                value=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr=val_ref_cast.spelling,
                    ctx=ast.Load()),
                attr='val',
                ctx=ast.Load())
        else:
            raise AssertionError()
        var_pyast = ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr=decl_ref_cast.spelling,
                ctx=ast.Load()),
            attr='val',
            ctx=ast.Store())
        stmts_pyast.append(ast.Assign(
            targets=[var_pyast],
            value=val))
    return ast.FunctionDef(
        name=func_decl_cast.spelling,
        decorator_list=[],
        args=ast.arguments(args=[ast.Name(id='self', ctx=ast.Param())],
                           vararg=None,
                           kwarg=None,
                           defaults=[]),
        body=stmts_pyast or [ast.Pass()])

def parse_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    members_pyast = []
    for decl_cast in transunit.cursor.get_children():
        if decl_cast.kind.name == 'VAR_DECL':
            members_pyast.append(parse_var_decl(decl_cast))
        elif decl_cast.kind.name == 'FUNCTION_DECL':
            members_pyast.append(parse_func_decl(decl_cast))
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
    module_pyast = parse_transunit(transunit)
    ast.fix_missing_locations(module_pyast)
    module_pyc = compile(module_pyast, 'transunit_filename.c', 'exec')
    module = dict()
    exec module_pyc in module
    return module['TransUnitCls']


config_clang()