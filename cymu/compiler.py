import ast
import functools
import os

import clang.cindex

# this value is vor debugging purposes.
# It prints the python AST of compiled C-code
PRINT_PYAST = False


TYPE_MAP = {
    clang.cindex.TypeKind.CHAR_S: 'char',
    clang.cindex.TypeKind.UCHAR: 'unsigned_char',
    clang.cindex.TypeKind.SHORT: 'short',
    clang.cindex.TypeKind.USHORT: 'unsigned_short',
    clang.cindex.TypeKind.INT: 'int',
    clang.cindex.TypeKind.UINT: 'unsigned_int',
    clang.cindex.TypeKind.LONG: 'long',
    clang.cindex.TypeKind.ULONG: 'unsigned_long' }


class CompileError(Exception):
    pass


class CompileContext(dict):

    def __getattr__(self, name):
        return self.get(name)


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
        def astconv_wrapper(astc, ctx, prefix_stmts):
            pyast = astconv_func(astc, ctx, prefix_stmts)
            pyast.lineno = astc.location.line
            pyast.col_offset = astc.location.column - 1
            return pyast
        return astconv_wrapper
    return decorator

def src_location_end_marker(astc):
    return ast.Pass(
        lineno=astc.extent.end.line,
        col_offset=astc.extent.end.column - 1)

def fix_src_locations(node_list):
    """
    To ensure that all debug-linenos are in ascending order (required by python)
    all ast-nodes WITHOUT location (usually prefix-stmts) get the
    location of the next ast-node following WITH location.

    :param list[ast.AST] stmt_list: list of AST nodes that shall be written in
                                    ascending order
    :rtype: list[ast.AST]
    """
    for next_astpy, prev_astpy in reversed(zip(node_list[1:], node_list[:-1])):
        if not hasattr(prev_astpy, 'lineno'):
            ast.copy_location(prev_astpy, next_astpy)


def attr(obj, *nested_attrnames):
    if isinstance(obj, str):
        expr_astpy = ast.Name(id=obj, ctx=ast.Load())
    elif isinstance(obj, ast.AST):
        expr_astpy = obj
    else:
        raise AssertionError('invalid type of "obj"')
    for attrname in nested_attrnames:
        expr_astpy = ast.Attribute(
            value=expr_astpy,
            attr=attrname,
            ctx=ast.Load())
    return expr_astpy

def call(obj, *args):
    return ast.Call(
        func=obj,
        args=list(args),
        keywords=[],
        starargs=None,
        kwargs=None)

def astconv_expr(expr_astc, ctx, prefix_stmts):
    children = list(expr_astc.get_children())
    if expr_astc.kind.name in ('BINARY_OPERATOR', 'COMPOUND_ASSIGNMENT_OPERATOR'):
        decl_ref_astc, val_astc = children
        lvalue_astpy = astconv_expr(decl_ref_astc, ctx, prefix_stmts)
        lval_val_astpy = ast.Attribute(
            value=lvalue_astpy,
            attr='val',
            ctx=ast.Store())
        if expr_astc.kind.name == 'BINARY_OPERATOR':
            assert expr_astc.operator_kind.name == 'ASSIGN'
            prefix_stmts.append(ast.Assign(
                targets=[lval_val_astpy],
                value=astconv_expr(val_astc, ctx, prefix_stmts)))
        else:
            assert expr_astc.operator_kind.name == 'SUB_ASSIGN'
            prefix_stmts.append(ast.AugAssign(
                target=lval_val_astpy,
                op=ast.Sub(),
                value=astconv_expr(val_astc, ctx, prefix_stmts)))
        return lvalue_astpy
    elif expr_astc.kind.name == 'INTEGER_LITERAL':
        int_tok_astc = expr_astc.get_tokens().next()
        int_astpy = ast.Num(n=int(int_tok_astc.spelling))
        return call(attr('__globals__', 'int'), int_astpy)
    elif expr_astc.kind.name == 'UNEXPOSED_EXPR':
        [sub_astc] = children
        return astconv_expr(sub_astc, ctx, prefix_stmts)
    elif expr_astc.kind.name == 'DECL_REF_EXPR':
        if ctx.local_names is not None and \
                        expr_astc.spelling in ctx.local_names:
            return attr(expr_astc.spelling)
        else:
            return attr('__globals__', expr_astc.spelling)
    elif expr_astc.kind.name == 'MEMBER_REF_EXPR':
        struct_astpy = astconv_expr(children[0], ctx, prefix_stmts)
        return attr(struct_astpy, expr_astc.spelling)
    elif expr_astc.kind.name == 'INIT_LIST_EXPR':
        # only valid for initializing lists/struct variables
        return ast.Tuple(
                elts=[astconv_expr(child, ctx, prefix_stmts)
                      for child in children],
                ctx=ast.Load())
    else:
        raise CompileError('Unsupportet Expression {!r}'
                            .format(expr_astc.kind.name))

@with_src_location()
def astconv_var_decl(var_decl_astc, ctx, prefix_stmts):
    init_val_list = list(var_decl_astc.get_children())
    if var_decl_astc.type.spelling.startswith('struct '):
        c_struct_name = var_decl_astc.type.spelling.replace(' ', '_')
        type_astpy = attr('__globals__', c_struct_name)
        del init_val_list[0]
    else:
        type_astpy = attr('__globals__', TYPE_MAP[var_decl_astc.type.kind])
    if len(init_val_list) == 0:
        args = []
    else:
        arg = astconv_expr(init_val_list[0], ctx, prefix_stmts)
        if isinstance(arg, ast.Tuple):
            args = arg.elts
        else:
            args = [arg]
    if ctx.local_names is None:
        target = attr('__globals__', var_decl_astc.spelling)
    else:
        target = attr(var_decl_astc.spelling)
        ctx.local_names.add(var_decl_astc.spelling)
    target.ctx = ast.Store()
    return ast.Assign(
        targets=[target],
        value=call(type_astpy, *args))

def astconv_compound_stmt(comp_stmt_astc, ctx, prefix_stmts):
    for stmt_astc in comp_stmt_astc.get_children():
        if stmt_astc.kind.name == 'DECL_STMT':
            [child_astc] = stmt_astc.get_children()
            stmt_astpy = astconv_var_decl(child_astc, ctx, prefix_stmts)
        else:
            stmt_astpy = astconv_stmt(stmt_astc, ctx, prefix_stmts)
        prefix_stmts.append(stmt_astpy)
    return ast.Pass()

@with_src_location()
def astconv_if_stmt(if_stmt_astc, ctx, prefix_stmts):
    children = list(if_stmt_astc.get_children())
    return ast.If(
        test=astconv_expr(children[0], ctx, prefix_stmts),
        body=to_stmt_list(children[1], ctx),
        orelse=([] if len(children) != 3
                else to_stmt_list(children[2], ctx)))

@with_src_location()
def astconv_while_stmt(while_stmt_astc, ctx, prefix_stmts):
    [exit_cond_astc, body_astc] = while_stmt_astc.get_children()
    exit_check_prefix_stmts = []
    exit_check_astpy = ast.If(
        test=ast.UnaryOp(
            op=ast.Not(),
            operand=astconv_expr(exit_cond_astc, ctx,
                                 exit_check_prefix_stmts)),
        body=[ast.Break()],
        orelse=[])
    return ast.While(
        test=ast.Name(id='True', ctx=ast.Load()),
        body=exit_check_prefix_stmts + [exit_check_astpy] +
             to_stmt_list(body_astc, ctx),
        orelse=[])

@with_src_location()
def astconv_dowhile_stmt(dowhile_stmt_astc, ctx, prefix_stmts):
    [body_astc, exit_cond_astc] = dowhile_stmt_astc.get_children()
    exit_check_prefix_stmts = []
    exit_check_astpy = ast.If(
        test=ast.UnaryOp(
            op=ast.Not(),
            operand=astconv_expr(exit_cond_astc, ctx,
                                 exit_check_prefix_stmts)),
        body=[ast.Break()],
        orelse=[])
    return ast.While(
        test=ast.Name(id='True', ctx=ast.Load()),
        body=to_stmt_list(body_astc, ctx) +
             exit_check_prefix_stmts + [exit_check_astpy],
        orelse=[])

@with_src_location()
def astconv_return_stmt(return_stmt_astc, ctx, prefix_stmts):
    children = list(return_stmt_astc.get_children())
    if len(children) == 0:
        result_astpy = ast.None
    else:
        type_name = TYPE_MAP[ctx.func_result_type.kind]
        result_astpy = call(
            attr('__globals__', type_name, 'cast'),
            astconv_expr(children[0], ctx, prefix_stmts))
    return ast.Return(value=result_astpy)

@with_src_location()
def astconv_expr_as_stmt(stmt_astc, ctx, prefix_stmts):
    astconv_expr(stmt_astc, ctx, prefix_stmts)
    return ast.Pass()

def astconv_stmt(stmt_astc, ctx, prefix_stmts):
    if stmt_astc.kind.name == 'IF_STMT':
        return astconv_if_stmt(stmt_astc, ctx, prefix_stmts)
    elif stmt_astc.kind.name == 'NULL_STMT':
        return ast.Pass()
    elif stmt_astc.kind.name == 'WHILE_STMT':
        return astconv_while_stmt(stmt_astc, ctx, prefix_stmts)
    elif stmt_astc.kind.name == 'DO_STMT':
        return astconv_dowhile_stmt(stmt_astc, ctx, prefix_stmts)
    elif stmt_astc.kind.name == 'COMPOUND_STMT':
        return astconv_compound_stmt(stmt_astc, ctx, prefix_stmts)
    elif stmt_astc.kind.name == 'RETURN_STMT':
        return astconv_return_stmt(stmt_astc, ctx, prefix_stmts)
    else:
        return astconv_expr_as_stmt(stmt_astc, ctx, prefix_stmts)

def to_stmt_list(stmt_astc, ctx):
    stmt_list = []
    stmt_astpy = astconv_stmt(stmt_astc, ctx, prefix_stmts=stmt_list)
    if not isinstance(stmt_astpy, ast.Pass) or \
            hasattr(stmt_astpy, 'lineno') or \
            len(stmt_list) == 0:
        stmt_list.append(stmt_astpy)
    fix_src_locations(stmt_list)
    return stmt_list

@with_src_location()
def astconv_func_param(param_astc, ctx, prefix_stmts):
    return ast.Assign(
        targets=[ast.Name(id=param_astc.spelling, ctx=ast.Store())],
        value=call(attr('__globals__', TYPE_MAP[param_astc.type.kind]),
                   attr(param_astc.spelling)))

@with_src_location()
def astconv_func_decl(func_decl_astc, ctx, prefix_stmts):
    children = list(func_decl_astc.get_children())
    if any(c.kind.name == 'COMPOUND_STMT' for c in children):
        x = func_decl_astc.get_arguments()
        ctx.local_names = { param_astc.spelling
                            for param_astc in func_decl_astc.get_arguments() }
        ctx.func_result_type = func_decl_astc.result_type
        params_astpy = \
            [ast.Name(id='__globals__', ctx=ast.Param())] + \
            [ast.Name(id=param_astc.spelling, ctx=ast.Param())
             for param_astc in func_decl_astc.get_arguments()]
        vararg_astpy = (None if func_decl_astc.type.spelling.endswith('(void)')
                        else '_')
        casted_param_astpy = [
            astconv_func_param(param_astc, ctx, prefix_stmts)
            for param_astc in func_decl_astc.get_arguments()]
        func_astpy = ast.FunctionDef(
            name=func_decl_astc.spelling,
            decorator_list=[],
            args=ast.arguments(args=params_astpy,
                               vararg=vararg_astpy,
                               kwarg=None,
                               defaults=[]),
            body=casted_param_astpy +
                 to_stmt_list(children[-1], ctx=ctx) +
                 [src_location_end_marker(func_decl_astc)])
        del ctx.local_names
        del ctx.func_result_type
        return func_astpy
    else:
        return ast.Pass()

@with_src_location()
def astconv_struct_decl(struct_decl_astc, ctx, prefix_stmts):
    field_astpy_list = []
    for decl_astc in struct_decl_astc.get_children():
        if decl_astc.kind.name == 'FIELD_DECL':
            type_name = decl_astc.type.spelling
            if type_name.startswith('struct '):
                type_astpy = attr(type_name.replace(' ', '_'))
            else:
                type_astpy = attr('datamodel', 'CProgram',
                                  TYPE_MAP[decl_astc.type.kind])
            field_astpy_list.append(
                ast.Tuple(
                    elts=[ast.Str(s=decl_astc.spelling), type_astpy],
                    ctx=ast.Load()))
        elif decl_astc.kind.name == 'STRUCT_DECL':
            substruct_astpy = astconv_struct_decl(
                decl_astc, ctx, prefix_stmts)
            prefix_stmts.append(substruct_astpy)

    struct_name = 'struct_' + struct_decl_astc.spelling
    return ast.Assign(
        targets=[ast.Name(id=struct_name, ctx=ast.Store())],
        value=call(attr('datamodel', 'StructCType'),
                   ast.Str(s=struct_name),
                   ast.List(elts=field_astpy_list, ctx=ast.Load())))

def astconv_decl(decl_astc, ctx, prefix_stmts):
    if decl_astc.kind.name == 'VAR_DECL':
        return astconv_var_decl(decl_astc, ctx, prefix_stmts)
    elif decl_astc.kind.name == 'FUNCTION_DECL':
        return astconv_func_decl(decl_astc, ctx, prefix_stmts)
    elif decl_astc.kind.name == 'STRUCT_DECL':
        return astconv_struct_decl(decl_astc, ctx, prefix_stmts)
    else:
        raise CompileError('Unsupportet Declaration {!r}'
                           .format(decl_astc.kind.name))

def get_ast_of_transunit(transunit):
    """
    Compile a clang.cindex.

    :param clang.cindex.TranslationUnit transunit: Source code that will be
        tranlated to program object
    :return: datamodel.Program prog
    """
    non_var_decls_astpy = []
    var_decls_astpy = []
    ctx = CompileContext()
    for decl_astc in transunit.cursor.get_children():
        prefix_stmts = []
        decl_astpy = astconv_decl(decl_astc, ctx, prefix_stmts)
        decls_astpy = (var_decls_astpy if decl_astc.kind.name == 'VAR_DECL'
                       else non_var_decls_astpy)
        decls_astpy += prefix_stmts
        decls_astpy.append(decl_astpy)
    fix_src_locations(non_var_decls_astpy)
    fix_src_locations(var_decls_astpy)
    if len(var_decls_astpy) == 0:
        var_decls_astpy.append(ast.Pass())

    class_def_astpy = ast.ClassDef(
        name='CModule',
        decorator_list=[],
        bases=[attr('datamodel', 'CProgram')],
        body=non_var_decls_astpy + [ast.FunctionDef(
            name='global_vars',
            decorator_list=[],
            args=ast.arguments(args=[ast.Name(id='__globals__',
                                              ctx=ast.Param())],
                               vararg=None,
                               kwarg=None,
                               defaults=[]),
            body=var_decls_astpy)])
    module_astpy = ast.Module(body=[
        ast.ImportFrom(module='cymu',
                       names=[ast.alias(name='datamodel', asname=None)]),
        class_def_astpy])
    return module_astpy

def compile_transunit(transunit):
    module_astpy = get_ast_of_transunit(transunit)
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
