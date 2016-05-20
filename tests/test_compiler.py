import pytest
import clang.cindex
import compiler
import datamodel


def compile_ccode(c_src):
    index = clang.cindex.Index.create()
    transunit = index.parse('test.c', unsaved_files=[('test.c', c_src)])
    assert len(list(transunit.diagnostics)) == 0
    compiled_transunit_cls = compiler.compile_transunit(transunit)
    return compiled_transunit_cls()

def test_varDecl_inGlobalScope_addsVarDefToProgramType():
    prog = compile_ccode('int a;')
    assert isinstance(prog.a, datamodel.CInt)

def test_varDecl_inGlobalScopeMultipleVars_addsVarDefsToProgramType():
    prog = compile_ccode('int a, b; int c;')
    assert isinstance(prog.a, datamodel.CInt)
    assert isinstance(prog.b, datamodel.CInt)
    assert isinstance(prog.c, datamodel.CInt)

def test_funcDef_addsMethodToProgramType():
    prog = compile_ccode('void f() {}')
    prog.f()

def test_assignment_onGlobalVarInFunc_changesGlobalVarInFuncCall():
    prog = compile_ccode('int a; void f() { a = 10; }')
    prog.f()
    assert prog.a.val == 10
