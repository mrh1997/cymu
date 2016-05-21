import pytest
import clang.cindex
from cymu import datamodel, compiler


def compile_ccode(c_src):
    compiled_transunit_cls = compiler.compile_str(c_src, 'test.c')
    return compiled_transunit_cls()

def test_varDecl_inGlobalScope_addsVarDefToProgramType():
    prog = compile_ccode('int a;')
    assert isinstance(prog.a, datamodel.CInt)

def test_varDecl_inGlobalScopeMultipleVars_addsVarDefsToProgramType():
    prog = compile_ccode('int a; int b, c;')
    assert isinstance(prog.a, datamodel.CInt)
    assert isinstance(prog.b, datamodel.CInt)
    assert isinstance(prog.c, datamodel.CInt)

def test_varDecl_inGlobalScopeWithInitialization_setsInitialValueOfVar():
    prog = compile_ccode('int a = 10;')
    assert prog.a.val == 10

def test_funcDef_addsMethodToProgramType():
    prog = compile_ccode('void f() {}')
    prog.f()

def test_assignment_onGlobalVar_changesGlobalVarInFuncCall():
    prog = compile_ccode('int a; void f() { a = 10; }')
    prog.f()
    assert prog.a.val == 10

def test_eval_onGlobalVar_rerievesContentOfGlobalVar():
    prog = compile_ccode('int a = 10, b; void f() { b = a; }')
    prog.f()
    assert prog.b.val == 10

def test_funcDef_addsDebugInfo():
    prog = compile_ccode('int a, b, c;\n'
                         'void f() {\n'
                         '    a=1;\n'
                         '    b=2;\n'
                         '    c=3;\n'
                         '}')
    assert prog.f.__func__.__code__.co_filename == 'test.c'
    line_tab = prog.f.__func__.__code__.co_lnotab
    assert len(line_tab) == 2*3
    assert all(ord(line_cnt) == 1 for line_cnt in line_tab[1::2])
