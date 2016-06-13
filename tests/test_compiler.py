import pytest

from cymu import compiler
from cymu.datamodel import CProgram, StructCType, IntCObj


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
    assert prog.a.ctype == CProgram.int
    assert prog.b.ctype == CProgram.int
    assert prog.c.ctype == CProgram.int

### inner scope overwrites variable of same name of outer scope

### local assignment shall not replace CObject but only contained pyobj

def test_varDecl_inGlobalScopeWithInitialization_setsInitialValueOfVar():
    prog = compile_ccode('int outp = 10;')
    assert prog.outp.val == 10

def test_varDecl_inGlobalScopeWithInitializationWithBrackets_setsInitialValueOfVar():
    prog = compile_ccode('int outp = { 10 };')
    assert prog.outp.val == 10

def test_emptyStmt_ok():
    run_ccode(';')

def test_assignmentOp_onGlobalVar_changesGlobalVarInFuncCall():
    prog = run_ccode('outp = 10;', outp=None)
    assert prog.outp.val == 10

def test_eval_onIntConstant_returnsCInt():
    class MyIntCObj(IntCObj):
        val = None    # replace property by simple val, which can be overwritten
    prog = compile_ccode('int outp; void func() { outp = 3; }')
    prog.outp = MyIntCObj(prog.__adr_space__, CProgram.int)
    prog.func()
    int_const = prog.outp.val
    assert isinstance(int_const, IntCObj)
    assert int_const.val == 3

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

def test_varDecl_inLocalScope_doesCorrectAssignment():
    prog = run_ccode('int a; a = 11; outp = a;', outp=None)
    assert prog.outp.val == 11

def test_varDecl_inLocalScope_doesNotAddVarToProgramTypeOrGlobalScope():
    prog = run_ccode('int a; a = 11;')
    assert not hasattr(prog, 'a')
    assert 'a' not in globals()

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

def test_funcDecl_withParamAndNoParamPassed_raisesTypeError():
    prog = compile_ccode('void f(int p) { }')
    with pytest.raises(TypeError):
        prog.f()

def test_funcDecl_withParam_canAccessParam():
    prog = compile_ccode(
        'int outp;\n'
        'void f(int p) { outp = p; }\n')
    prog.f(1234)
    assert prog.outp == 1234

def test_funcDecl_withParamModifiedInBody_doesNotChangeCallersValue():
    prog = compile_ccode(
        'int outp;\n'
        'void f(int p) { p = 2; outp = p; }\n')
    inp = prog.int(1)
    prog.f(inp)
    assert inp == 1
    assert prog.outp == 2

def test_funcDecl_onParamOfWrongType_willCastParam():
    prog = compile_ccode(
        'int outp;\n'
        'void f(unsigned char p) { outp = p; }\n')
    prog.f(-1)
    assert prog.outp == 0xFF

def test_funcDecl_onMultipleParams_passedInCorrectOrder():
    prog = compile_ccode(
        'int outp1, outp2;\n'
        'void f(int p1, int p2) { outp1 = p1; outp2 = p2; }\n')
    prog.f(11, 22)
    assert prog.outp1 == 11
    assert prog.outp2 == 22

def test_funcDecl_onVoidParamListAndParamPassed_raisesTypeError():
    prog = compile_ccode('void f(void) { }\n')
    with pytest.raises(TypeError):
        prog.f(1)

def test_funcDecl_onEmptyParamListAndParamsPassed_ok():
    prog = compile_ccode('void f() { }\n')
    prog.f(1)
    prog.f(1, 2)

def test_returnStmt_withExpr_returnsExprAsResult():
    prog = compile_ccode('int f() { return 3; }')
    assert prog.f().ctype == prog.int
    assert prog.f() == 3

def test_returnStmt_withNonIntFunc_returnsNonCIntAsResult():
    prog = compile_ccode('char f() { return 9; }')
    assert prog.f().ctype == prog.char
    assert prog.f() == 9

def test_returnStmt_withDifferentTypeThanFunc_castsToCorrectType():
    prog = compile_ccode('int f() { char x = 3; return x; }')
    assert prog.f().ctype == prog.int
    assert prog.f() == 3

def test_structDef_returnCStructObj():
    prog = compile_ccode('struct s { };')
    struct_s = prog.struct_s
    assert isinstance(struct_s.base_ctype, StructCType)
    assert struct_s.name == 'struct_s'

def test_structDef_onDifferentTypeName():
    prog = compile_ccode('struct other_name { };')
    assert prog.struct_other_name.name == 'struct_other_name'

def test_structDef_withFields_setsFieldDefInPyClass():
    prog = compile_ccode("""
        struct s {
            int a;
            char b;
        } ;
    """)
    struct_ctype = prog.struct_s
    assert struct_ctype.fields == [('a', CProgram.int), ('b', CProgram.char)]

def test_structDef_withVarDecl_addsVarDeclToGlobal():
    prog = compile_ccode("""
        struct s {
            int a;
        } s;
    """)
    assert prog.s.a.ctype == CProgram.int

def test_structDef_withVarDeclByReference_addsVarDeclToGlobal():
    prog = compile_ccode("""
        struct s {
            int a;
        } ;
        struct s s;
    """)
    assert prog.s.a.ctype == CProgram.int

def test_structDef_withNestedStruct():
    prog = compile_ccode("""
        struct s {
            struct nested_t {
                int a;
            } nested;
            int b;
        };
    """)
    assert prog.struct_s.fields == \
           [('nested', prog.struct_nested_t.base_ctype), ('b', CProgram.int)]

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

def test_structInitialization():
    prog = compile_ccode("""
        struct s {
            int a;
            char b;
        } s = { 1, 2 };
    """)
    assert prog.s.a == 1
    assert prog.s.b == 2

def test_structInitialization_onNestedStructs():
    prog = compile_ccode("""
        struct s {
            struct nested_t {
                int a;
            } nested;
            int b;
        } s = { { 1 }, 2 };
    """)
    assert prog.s.nested.a == 1
    assert prog.s.b == 2

### implement support for unnamed structs

### test source line map of struct definition (var defs in different lines!!!)
