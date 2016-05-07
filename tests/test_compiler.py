import pytest
import clang.cindex
import compiler
import datamodel


def compile(c_src):
    index = clang.cindex.Index.create()
    transunit = index.parse('test.c', unsaved_files=[('test.c', c_src)])
    assert len(list(transunit.diagnostics)) == 0
    progType = compiler.compile_transunit(transunit)
    return progType()

def test_varDecl_inGlobalScope_addsVarDefToProgramType():
    prog = compile('int a;')
    assert isinstance(prog.a, datamodel.CInt)

def test_varDecl_inGlobalScopeMultipleVars_addsVarDefsToProgramType():
    prog = compile('int a, b; int c;')
    assert isinstance(prog.a, datamodel.CInt)
    assert isinstance(prog.b, datamodel.CInt)
    assert isinstance(prog.c, datamodel.CInt)

def test_funcDef_addsMethodToProgramType():
    prog = compile('void f() {}')
    prog.f()
