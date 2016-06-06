import pytest

from cymu import compiler
from cymu.datamodel import CProgram, CStruct


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

def test_funcDecl_addsMethodToProgramType():
    prog = compile_ccode('void func() {}')
    prog.func()

def test_funcDecl_declarationOnly_ignoreDef():
    compile_ccode('int f();')

def test_varDecl_inGlobalScope_addsVarDefToProgramType():
    prog = compile_ccode('int a;')
    _ = prog.a

@pytest.mark.parametrize('name',
                         ['char', 'short', 'int', 'long',
                          'unsigned int', 'signed int',])
def test_varDecl_ofTypeX_createXCObj(name):
    prog = compile_ccode(name + ' a;')
    assert type(prog.a).__name__, name.replace(' ', '_')

def test_varDecl_inGlobalScopeMultipleVars_addsVarDefsToProgramType():
    prog = compile_ccode('int a; int b, c;')
    assert isinstance(prog.a, CProgram.int.base_type)
    assert isinstance(prog.b, CProgram.int.base_type)
    assert isinstance(prog.c, CProgram.int.base_type)

def test_varDecl_inLocalScope_doesCorrectAssignment():
    prog = run_ccode('int a; a = 11; outp = a;', outp=None)
    assert prog.outp.val == 11

def test_varDecl_inLocalScope_doesNotAddVarToProgramTypeOrGlobalScope():
    prog = run_ccode('int a; a = 11;')
    assert not hasattr(prog, 'a')
    assert 'a' not in globals()

### inner scope overwrites variable of same name of outer scope

### local assignment shall not replace CObject but only contained pyobj

def test_varDecl_inGlobalScopeWithInitialization_setsInitialValueOfVar():
    prog = compile_ccode('int outp = 10;')
    assert prog.outp.val == 10

def test_emptyStmt_ok():
    run_ccode(';')

def test_assignmentOp_onGlobalVar_changesGlobalVarInFuncCall():
    prog = run_ccode('outp = 10;', outp=None)
    assert prog.outp.val == 10

def test_eval_onIntConstant_returnsCInt():
    def convert_with_check(int_cobj):
        assert isinstance(int_cobj, CProgram.int.base_type)
        return int_cobj.val
    prog = compile_ccode('int outp; void func() { outp = 3; }')
    prog.outp.convert = convert_with_check
    prog.func()

def test_assignmentSubOp_ok():
    prog = run_ccode('inoutp -= 3;', inoutp=7)
    assert prog.inoutp == 4

def test_assignment_inExpr_ok():
    prog = run_ccode('outp2 = outp1 = inoutp0 -= 1;',
                     inoutp0=3, outp1=None, outp2=None)
    assert prog.inoutp0 == 2
    assert prog.outp1 == 2
    assert prog.outp2 == 2

def test_assignment_inGlobalVarDecl_raisesCompilerError():
    with pytest.raises(compiler.CompileError):
        compile_ccode('int a = 1; int b = (a += 1);')

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

def test_whileStmt_withPrefixStmt_executesPrefixStmtBeforeEveryLoop():
    prog = run_ccode('while (inp -= 1) ;', inp=3)

@pytest.mark.parametrize('loopcnt', (1, 2, 3))
def test_doWhileStmt_onNeverNonZeroCondition_doEnterLoopBlockOnce(loopcnt):
    prog = run_ccode('do { inoutp1 -= 1; inoutp2 -= 1; } while (inoutp1);',
                     inoutp1=loopcnt, inoutp2=0)
    assert prog.inoutp2.val == -loopcnt

def test_doWhileStmt_withPrefixStmt_executesPrefixStmtBeforeEveryLoop():
    prog = run_ccode('do ; while (inp -= 1);', inp=3)

def get_linenos(func):
    assert func.__func__.__code__.co_filename == 'test.c'
    linenos = [func.__func__.__code__.co_firstlineno]
    for lineno_offset in func.__func__.__code__.co_lnotab[1::2]:
        if lineno_offset != '\0':
            linenos.append(linenos[-1] + ord(lineno_offset))
    return linenos

def test_funcDecl_withOneLiners_hasConsecutiveSourceLineNoReferences():
    prog = compile_ccode("""  // this is line 1
        int a, b;
        void func() {
            a = 1;
            b -= 2;
        }""")
    assert get_linenos(prog.func) == range(3, 7)

def test_funcDecl_withSpaceLine_skipsSourceLineNoReference():
    prog = compile_ccode("""  // this is line 1
        int a, b;
        void func() {


            a = 1;

            b = 2;
        }""")
    assert get_linenos(prog.func) == [3, 6, 8, 9]

def test_funcDecl_bracketsFromCompoundStmt_doesNot():
    prog = compile_ccode("""  // this is line 1
        int a;
        void func() {
            {
                a = 1;
            }
        }""")
    assert get_linenos(prog.func) == [3, 5, 7]

def test_funcDecl_withWhileStmtWithPrefixStmt_hasNoSourceLineNoReferenceForComparisonCode():
    prog = compile_ccode("""  // this is line 1
        int a = 10, b = 0;
        void func() {
            while (a -= 1)
            {
                b -= 1;
            }
        }""")
    assert get_linenos(prog.func) == [3, 4, 6, 8]

def test_structDef_returnCStruct():
    prog = compile_ccode('struct s { };')
    struct_s = prog.struct_s.base_type
    assert issubclass(struct_s, CStruct)
    assert struct_s.__name__ == 'struct_s'

def test_structDef_withFields_setsFieldDefInPyClass():
    prog = compile_ccode("""
        struct s {
            int a;
            char b;
        } ;
    """)
    struct_s = prog.struct_s.base_type
    assert struct_s.__FIELDS__ == [('a', CProgram.int), ('b', CProgram.char)]

def test_structDef_withVarDecl_addsVarDeclToGlobal():
    prog = compile_ccode("""
        struct s {
            int a;
        } s;
    """)
    assert isinstance(prog.s.a, CProgram.int.base_type)

def test_structAttr_inAssignmentDest_changesField():
    prog = compile_ccode("""
        struct s {
            int a;
        } s;
        void func() {
            s.a = 10;
        }
    """)
    prog.func()
    assert prog.s.a == 10

def test_structAttr_inAssignmentSrc_readsField():
    prog = compile_ccode("""
        struct s {
            int a;
        } s;
        int outp;
        void func() {
            s.a = 10;
            outp = s.a;
        }
    """)
    prog.func()
    assert prog.outp == 10

### test support of nested structs

### test source line map of struct definition (var defs in different lines!!!)

### test support for struct initialization

### test support for nested struct initialization

### test compare with "assert short(-1) > long(100)"