import pytest
from cymu import datamodel, compiler


def compile_ccode(c_src):
    compiled_transunit_cls = compiler.compile_str(c_src, 'test.c')
    return compiled_transunit_cls()

def run_ccode(c_src, **vars):
    if len(vars) == 0:
        var_decls = ''
    else:
        var_decls = ('int ' +
                     ', '.join(name + ('' if val is None else ('=' + str(val)))
                               for name, val in vars.items()) +
                     ';\n')
    func_decl = 'void func() {\n' + c_src + '\n}'
    prog = compile_ccode(var_decls + func_decl)
    prog.func()
    return prog

def test_emptyModule_ok():
    prog = compile_ccode('')
    assert len([nm for nm in dir(prog) if not nm.startswith('__')]) == 0

def test_varDecl_inGlobalScope_addsVarDefToProgramType():
    prog = compile_ccode('int a;')
    assert isinstance(prog.a, datamodel.CInt)

def test_varDecl_inGlobalScopeMultipleVars_addsVarDefsToProgramType():
    prog = compile_ccode('int a; int b, c;')
    assert isinstance(prog.a, datamodel.CInt)
    assert isinstance(prog.b, datamodel.CInt)
    assert isinstance(prog.c, datamodel.CInt)

def test_varDecl_inGlobalScopeWithInitialization_setsInitialValueOfVar():
    prog = compile_ccode('int outp = 10;')
    assert prog.outp.val == 10

def test_funcDecl_addsMethodToProgramType():
    prog = compile_ccode('void func() {}')
    prog.func()

def test_funcDecl_declarationOnly_ignoreDef():
    compile_ccode('int f();')

def test_emptyStmt_ok():
    run_ccode(';')

def test_assignmentOp_onGlobalVar_changesGlobalVarInFuncCall():
    prog = run_ccode('outp = 10;', outp=None)
    assert prog.outp.val == 10

def test_assignmentSubOp_ok():
    prog = run_ccode('inoutp -= 3;', inoutp=7)
    assert prog.inoutp == 4

### test assignment as expr (a = b = c)

def test_eval_onGlobalVar_rerievesContentOfGlobalVar():
    prog = run_ccode('outp = inp;', inp=10, outp=None)
    assert prog.outp.val == 10

@pytest.mark.parametrize(('inp', 'outp_before', 'outp_after'), [(0, 11, 11),
                                                                (1, 11, 22)])
def test_ifStmt_onZeroCondition_doesNotEnterThenBlock(inp, outp_before, outp_after):
    prog = run_ccode('if (inp) outp = 22;', inp=inp, outp=outp_before)
    assert prog.outp.val == outp_after

@pytest.mark.parametrize(('inp', 'outp'), [(0, 33),
                                           (1, 22)])
def test_elseStmt_onZeroCondition_doesEnterElseBlock(inp, outp):
    prog = run_ccode('if (inp) outp = 22; else outp = 33;', inp=inp, outp=None)
    assert prog.outp.val == outp

def test_compoundStmt_onExpectedPyStmtList_runAll():
    prog = run_ccode('if (1) { outp1 = 1; outp2 = 2; }', outp1=None, outp2=None)
    assert prog.outp1.val == 1
    assert prog.outp2.val == 2

def test_compoundStmt_onExpectedPyStmtListButEmpty_ok():
    run_ccode('if (1) {}')

def test_compoundStmt_onExpectedSingleStmt_ok():
    prog = run_ccode('outp1 = 1;\n'
                     '{\n'
                     '    outp2 = 2;\n'
                     '    outp3 = 3;\n'
                     '}\n'
                     'outp4 = 4;',
                     outp1=None, outp2=None, outp3=None, outp4=None)
    assert prog.outp1.val == 1
    assert prog.outp2.val == 2
    assert prog.outp3.val == 3
    assert prog.outp4.val == 4

def test_compoundStmt_onExpectedSingleStmtButEmpty_ok():
    run_ccode('{}')


@pytest.mark.parametrize('loopcnt', (0, 1, 2))
def test_whileStmt_ok(loopcnt):
    prog = run_ccode('while (inoutp1) { inoutp1 -= 1; inoutp2 -= 1; }',
                     inoutp1=loopcnt, inoutp2=0)
    assert prog.inoutp2.val == -loopcnt

@pytest.mark.parametrize('loopcnt', (1, 2, 3))
def test_doWhileStmt_onNeverNonZeroCondition_doEnterLoopBlockOnce(loopcnt):
    prog = run_ccode('do { inoutp1 -= 1; inoutp2 -= 1; } while (inoutp1);',
                     inoutp1=loopcnt, inoutp2=0)
    assert prog.inoutp2.val == -loopcnt

def test_funcDecl_addsDebugInfo():
    prog = compile_ccode('int a, b, c;\n'
                         'void func() {\n'
                         '    a=1;\n'
                         '    b=2;\n'
                         '    c=3;\n'
                         '}')
    assert prog.func.__func__.__code__.co_filename == 'test.c'
    line_tab = prog.func.__func__.__code__.co_lnotab
    assert len(line_tab) == 2*3
    assert all(ord(line_cnt) == 1 for line_cnt in line_tab[1::2])
