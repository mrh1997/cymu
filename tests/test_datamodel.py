import pytest

from cymu.datamodel import CProgram, BoundCType, AddressSpace, VarAccessError, \
    CType, IntCObj, IntCType, StructCType, CObj


@pytest.fixture
def adr_space():
    return AddressSpace()


@pytest.fixture()
def bound_int(adr_space):
    return BoundCType(CProgram.int, adr_space)


class TestBoundCType(object):

    class MyCType(CType):
        class COBJ_TYPE(CObj):
            def __init__(self, ctype, adr_space, *args, **argv):
                cobj = super(TestBoundCType.MyCType.COBJ_TYPE, self).__init__(
                    ctype, adr_space)
                self.args = args
                self.argv = argv

    @pytest.fixture
    def bound_ctype(self, adr_space):
        ctype = self.MyCType('dummy')
        return BoundCType(ctype, adr_space)

    def test_call_returnsCObj(self, bound_ctype):
        cobj = bound_ctype()
        assert isinstance(cobj, self.MyCType.COBJ_TYPE)

    def test_call_setsAdrSpace(self, adr_space, bound_ctype):
        cobj = bound_ctype()
        assert cobj.adr_space is adr_space

    def test_call_withPositionalParams_forwardsParamsToBaseType(self, bound_ctype):
        cobj = bound_ctype(1, "2", 3)
        assert cobj.args == (1, "2", 3)

    def test_call_withKeywordParams_forwardsParamsToBaseType(self, bound_ctype):
        cobj = bound_ctype(arg1=1, arg2="2", arg3=3)
        assert cobj.argv == dict(arg1=1, arg2="2", arg3=3)

    def test_repr(self, bound_ctype):
        assert repr(bound_ctype) == "<bound CType 'dummy'>"

    def test_getAttr_retursAttrOfCType(self, bound_ctype):
        assert bound_ctype.cast.__func__ is \
               bound_ctype.base_ctype.cast.__func__


class TestCType(object):

    @pytest.fixture()
    def implicit_cast(self):
        return IntCType.create_implicit_caster(CProgram.int,
                                               CProgram.unsigned_int)

    def test_bind_returnsBoundCType(self, adr_space):
        ctype = CProgram.int
        bound_ctype = ctype.bind(adr_space)
        assert isinstance(bound_ctype, BoundCType)
        assert bound_ctype.adr_space is adr_space
        assert bound_ctype.base_ctype is ctype

    def test_repr(self):
        assert repr(CProgram.int) == "<CType 'int'>"

    def test_implicitCast_onDifferentSigns_returnsUnsignedCObjs(self, implicit_cast, adr_space):
        signed_int1 = CProgram.int(adr_space, 1)
        signed_int2 = CProgram.int(adr_space, 2)
        unsigned_int3 = CProgram.unsigned_int(adr_space, 3)
        assert implicit_cast(signed_int1, signed_int2, unsigned_int3) == [
            CProgram.unsigned_int(adr_space, 1),
            CProgram.unsigned_int(adr_space, 2),
            CProgram.unsigned_int(adr_space, 3) ]

    def test_implicitCast_onPyInt_returnsSignedCObj(self, implicit_cast, adr_space):
        assert implicit_cast(1) == [CProgram.unsigned_int(adr_space, 1)]


class TestIntCObj(object):

    CINTEGER_RANGES = [
        (CProgram.char, -0x80, 0x7F),
        (CProgram.unsigned_char, 0x00, 0xFF),
        (CProgram.short, -0x8000, 0x7FFF),
        (CProgram.unsigned_short, 0x0000, 0xFFFF),
        (CProgram.int, -0x80000000, 0x7FFFFFFF),
        (CProgram.unsigned_int, 0x00000000, 0xFFFFFFFF)]

    def test_init_withParam_returnsInitializedCObj(self, bound_int):
        cobj = bound_int(11)
        assert cobj.initialized

    def test_init_withoutParam_returnsUninitializedCObj(self, bound_int):
        cobj = bound_int()
        assert not cobj.initialized

    def test_init_withParam_setsC(self, adr_space):
        calls_to_setc = []
        class MyIntCObj(IntCObj):
            def setc(self, new_value):
                calls_to_setc.append(new_value)
            val = property(fset=setc)
        MyIntCObj(CProgram.int, adr_space, 3)
        assert calls_to_setc == [3]

    def test_init_withIntCObj_ok(self, bound_int):
        cobj = bound_int(bound_int(11))
        assert int(cobj) == 11

    def test_int_onInitializedObj_returnsPyObj(self, bound_int):
        cobj = bound_int(22)
        assert int(cobj) == 22

    def test_int_onUnInitializedObj_raisesVarAccessError(self, bound_int):
        cobj = bound_int()
        with pytest.raises(VarAccessError):
            int(cobj)

    def test_getVal_onInitializedObj_returnsContentAsPyObj(self, bound_int):
        assert bound_int(3).val == 3

    def test_getVal_onUninitializedObj_raisesVarAccessError(self, bound_int):
        with pytest.raises(VarAccessError):
            _ = bound_int().val

    def test_setVal_withIntCObj_ok(self, bound_int, adr_space):
        cobj = bound_int()
        cobj.val = bound_int(11)
        assert int(cobj) == 11

    def test_setVal_withInt_ok(self, bound_int, adr_space):
        cobj = bound_int()
        cobj.val = 11
        assert int(cobj) == 11

    def test_setVal_withNonInt_raisesTypeError(self, bound_int):
        cint = bound_int()
        with pytest.raises(TypeError):
            cint.val = "1"

    def test_setVal_onUnitializedState_switchesToInitializedState(self, bound_int):
        cint = bound_int()
        cint.val = 1
        assert cint.initialized

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_setVal_onExceedsDefinitionRange_forceToMatch(self, adr_space, ctype, max, min):
        def as_cint(value):
            cobj = ctype(adr_space)
            cobj.val = value
            return int(cobj)
        assert as_cint(max) == max
        assert as_cint(max + 1) == min
        assert as_cint(min) == min
        assert as_cint(min - 1) == max
        assert as_cint((max + 1) * 4 + 123) == 123

    def test_initialized_onInitializedCObj_returnsTrue(self, bound_int):
        assert bound_int(11).initialized

    def test_initialized_onUninitializedCObj_returnsFalse(self, bound_int):
        assert not bound_int().initialized

    def test_cast_onPyInt_returnsIntCObj(self, adr_space):
        cobj = CProgram.short.cast(123, adr_space)
        assert isinstance(cobj, IntCObj)
        assert cobj.ctype == CProgram.short
        assert int(cobj) == 123

    def test_cast_onCObj_returnsIntCObj(self, bound_int):
        cobj = CProgram.short.cast(bound_int(123), adr_space)
        assert isinstance(cobj, IntCObj)
        assert cobj.ctype == CProgram.short
        assert int(cobj) == 123

    def test_cast_onCObjWithoutAdrSpaceParam_takesAdrSpaceFromCObj(self, bound_int, adr_space):
        cobj = CProgram.short.cast(bound_int(1))
        assert cobj.adr_space is adr_space

    def test_cast_onCObjWithDifferentAdrSpaceParam_createsNewObjWithNewAdrSpace(self, bound_int, adr_space):
        new_adr_space = AddressSpace()
        cobj = CProgram.int.cast(bound_int(1), adr_space=new_adr_space)
        assert cobj.adr_space is new_adr_space

    def test_cast_onCObjWithSameType_doesNotCreateNewObj(self, bound_int):
        cobj = bound_int(1)
        new_cobj = CProgram.int.cast(cobj)
        assert cobj is new_cobj

    def test_repr(self, bound_int):
        cobj = bound_int()
        assert repr(cobj) == 'int()'

    def test_repr_onInitializedObj(self, bound_int):
        cobj = bound_int(3)
        assert repr(cobj) == 'int(3)'

    def test_cmp_withPyObj_ok(self, bound_int):
        cobj = bound_int(1)
        assert cobj == 1
        assert 0 < cobj < 2
        assert 1 <= cobj <= 1
        assert not 0 > cobj

    def test_cmp_withCObj_ok(self, bound_int):
        cobj = bound_int(1)
        assert cobj == bound_int(1)
        assert bound_int(0) < cobj < bound_int(2)
        assert bound_int(1) <= cobj <= bound_int(1)
        assert not bound_int(0) > cobj

    def test_cmp_onImplicitTypeCast(self, adr_space):
        uint_3 = CProgram.unsigned_int(adr_space, 3)
        int_minus1 = CProgram.int(adr_space, -1)
        assert uint_3 < int_minus1     # -1 is casted to 0xFFFFFFFF!

    def test_nonZero_onZeroData_returnsFalse(self, bound_int):
        cobj = bound_int(0)
        assert not cobj

    def test_nonZero_onNonZeroData_returnsTrue(self, bound_int):
        cobj = bound_int(3)
        assert cobj

    def test_sub_withPyObj(self, bound_int):
        cobj = bound_int(5) - 3
        assert int(cobj) == 2

    def test_sub_withCObj(self, bound_int):
        cobj = bound_int(5) - bound_int(3)
        assert int(cobj) == 2

    def test_sub_onSignedAndUnsignedCObj_returnsInUnsignedCObj(self, adr_space):
        c_signed_int = CProgram.int(adr_space, 5)
        c_unsigned_int = CProgram.unsigned_int(adr_space, 3)
        cobj = c_signed_int - c_unsigned_int
        assert cobj.ctype == CProgram.unsigned_int

    def test_sub_onSmallCObj_widensResult(self, adr_space):
        c_char_plus100 = CProgram.char(adr_space, 100)
        c_char_minus100 = CProgram.char(adr_space, -100)
        cobj = c_char_minus100 - c_char_plus100
        assert int(cobj) == -200
        assert cobj.ctype == CProgram.int

    def test_sub_copiesAdrSpace(self, adr_space):
        c_char_5 = CProgram.char(adr_space, 5)
        cobj = c_char_5 - 3
        assert cobj.adr_space == adr_space

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, adr_space, ctype, min, max):
        cobj = ctype(adr_space, min)
        cobj -= 1
        assert int(cobj) == max

    def test_rsub_withPyObj(self, bound_int):
        cobj = 5 - bound_int(3)
        assert int(cobj) == 2

    def test_rsub_withPyObj_convertsPyObjToMachineWord(self, adr_space):
        cobj = CProgram.char(adr_space, 100)
        result = 500 - cobj
        assert int(result) == 400

    def test_isub_withPyObj(self, bound_int):
        cobj = bound_int(5)
        cobj_id = id(cobj)
        cobj -= 3
        assert int(cobj) == 2
        assert id(cobj) == cobj_id

    def test_isub_withCObj(self, bound_int):
        cobj = bound_int(5)
        cobj_id = id(cobj)
        cobj -= bound_int(3)
        assert int(cobj) == 2
        assert id(cobj) == cobj_id

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, adr_space, ctype, min, max):
        cobj = ctype(adr_space, min)
        cobj -= 1
        assert int(cobj) == max

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementMaxValByOne_returnsMinVal(self, adr_space, ctype, min, max):
        cobj = ctype(adr_space, max)
        cobj -= -1
        assert int(cobj) == min

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementZeroByMultipleMax_returnsZero(self, adr_space, ctype, min, max):
        cobj = ctype(adr_space, 0)
        cobj -= (max + 1) * 4
        assert int(cobj) == 0

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementZeroByMultipleMax_returnsZero(self, adr_space, ctype, min, max):
        cobj = ctype(adr_space, 0)
        cobj -= (max + 1) * 4
        assert int(cobj) == 0


class TestCStruct(object):

    @pytest.fixture
    def struct_simple(self):
        return StructCType('struct_simple', [
            ('a', CProgram.int),
            ('b', CProgram.short)])

    @pytest.fixture
    def struct_nested(self, struct_simple):
        return StructCType('struct_nested', [
            ('field', CProgram.int),
            ('inner_struct', struct_simple)])

    def test_create_createsCObjForEveryField(self, adr_space, struct_simple):
        cobj = struct_simple(adr_space)
        assert cobj.a.ctype == CProgram.int
        assert cobj.b.ctype == CProgram.short

    def test_create_withoutArgs_createsUninitializedFields(self, adr_space, struct_simple):
        cobj = struct_simple(adr_space)
        assert not cobj.a.initialized
        assert not cobj.initialized

    def test_create_withPositionaArgs_initializesFieldsByPosition(self, adr_space, struct_simple):
        cobj = struct_simple(adr_space, 1, 2)
        assert cobj.a == 1
        assert cobj.b == 2

    def test_create_withKeywordArgs_initializesFieldsByPosition(self, adr_space, struct_simple):
        cobj = struct_simple(adr_space, b=1, a=2)
        assert cobj.a == 2
        assert cobj.b == 1

    def test_create_withPartialProvidedArgsOnly_initializesMissingFieldsWith0(self, adr_space, struct_simple):
        cobj = struct_simple(adr_space, 1)
        assert cobj.b == 0

    def test_initialized_onPartiallyInitializedMembers_returnsFalse(self, struct_simple):
        cobj = struct_simple(adr_space)
        cobj.a.val = 1
        assert not cobj.initialized

    def test_initialized_onCompletelyInitializedMembers_returnsTrue(self, struct_simple):
        cobj = struct_simple(adr_space)
        cobj.a.val = 1
        cobj.b.val = 1
        assert cobj.initialized

    def test_create_onNestedStruct_recursiveCreatesInnerStruct(self, adr_space, struct_simple, struct_nested):
        cobj = struct_nested(adr_space)
        assert cobj.inner_struct.ctype == struct_simple

    def test_create_onNestedStructWithPartialProvidedArgs_clearsInnerStructs(self, adr_space, struct_simple, struct_nested):
        cobj = struct_nested(adr_space, 1)
        assert cobj.inner_struct.a == 0
        assert cobj.inner_struct.b == 0

    ### test .initialized on structs

    @pytest.mark.xfail()
    def test_create_onNestedStructWithProvidedInnerStructsAsCObj(self, adr_space, struct_simple, struct_nested):
        cobj = struct_nested(adr_space, 1, struct_simple(adr_space, 2, 3))
        assert cobj.field == 1
        assert cobj.inner_struct.a == 2
        assert cobj.inner_struct.b == 3

    @pytest.mark.xfail()
    def test_repr_onInitialized_returnsDataAsOrderedKeywordInitializers(self, adr_space, struct_simple, struct_nested):
        cobj = self.struct_nested(adr_space, 3, struct_simple(b=10))
        assert repr(cobj) == \
               'struct_nested(field=3, inner_struct=struct_simple(a=0, b=10))'


class TestCProgram(object):

    def test_create_onTypedefMemeber_createsBoundCTypes(self):
        class ProgramWithTypeDef(CProgram):
            typedef = CProgram.int
        prog = ProgramWithTypeDef()
        assert isinstance(prog.typedef, BoundCType)
        assert prog.typedef.base_ctype is CProgram.int

    def test_create_onVarMember_createsInstanceVars(self):
        class ProgramWithVar(CProgram):
            def global_vars(self):
                super(ProgramWithVar, self).global_vars()
                self.var = self.int()
        prog = ProgramWithVar()
        assert isinstance(prog.var, IntCObj)

    def test_create_onVarMemberOfCustomTypeDef_createsInstanceVars(self):
        class ProgramWithVar(CProgram):
            typedef = CProgram.int
            def global_vars(self):
                super(ProgramWithVar, self).global_vars()
                self.var = self.typedef()
        prog = ProgramWithVar()
        assert isinstance(prog.var, IntCObj)
