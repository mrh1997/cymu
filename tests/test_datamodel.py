import pytest

from cymu.datamodel import CProgram, CObject, CType, BoundCType, CStruct, \
    AddressSpace, VarAccessError


@pytest.fixture
def adr_space():
    return AddressSpace()


@pytest.fixture()
def bound_int(adr_space):
    return BoundCType(CProgram.int, adr_space)


class TestCObject(object):

    def test_init_withPyObj_ok(self, bound_int):
        c_obj = bound_int(11)
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_init_withCObj_ok(self, bound_int):
        c_obj = bound_int(bound_int(11))
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_setVal_withPyObj_ok(self, bound_int, adr_space):
        c_obj = bound_int()
        c_obj.val = 11
        assert c_obj.val == 11

    def test_setVal_withCObj_ok(self, bound_int, adr_space):
        c_obj = bound_int()
        c_obj.val = bound_int(11)
        assert c_obj.val == 11

    def test_initialized_onInitializedCObj_returnsTrue(self, bound_int):
        assert bound_int(11).initialized

    def test_initialized_onUninitializedCObj_returnsFalse(self, bound_int):
        assert not bound_int().initialized

    def test_checkedVal_onInitializedCObj_returnsVal(self, bound_int):
        assert bound_int(11).checked_val == 11

    def test_checkedVal_onUninitializedCObj_raisesVarAccessError(self, bound_int):
        with pytest.raises(VarAccessError):
            _ = bound_int().checked_val

    def test_setDescriptor_raisesVarAccessError(self, bound_int):
        class Container(object):
            var = bound_int()
        container = Container()
        with pytest.raises(VarAccessError):
            container.var = 3

    def test_repr(self, bound_int):
        c_obj = bound_int()
        assert repr(c_obj) == 'int()'

    def test_repr_onInitializedObj(self, bound_int):
        c_obj = bound_int(3)
        assert repr(c_obj) == 'int(3)'


class TestBoundCType(object):

    def test_call_returnsCObj(self, bound_int):
        cobj = bound_int()
        assert isinstance(cobj, bound_int.base_type)

    def test_call_withPositionalParams_forwardsParamsToBaseType(self, bound_int):
        cobj = bound_int(3)
        assert cobj.val == 3

    def test_call_withKeywordParams_forwardsParamsToBaseType(self, bound_int):
        cobj = bound_int(init_val=3)
        assert cobj.val == 3

    def test_repr(self, bound_int):
        assert repr(bound_int) == "<bound class 'cymu.datamodel.int'>"


class TestCType(object):

    def test_init_withCType_setsBaseTypeAttr(self):
        c_type = CType(CProgram.int)
        assert c_type.base_type is CProgram.int

    def test_bind_returnsBoundCType(self, adr_space):
        c_type = CType(CProgram.int)
        bound_c_type = c_type.bind(adr_space)
        assert isinstance(bound_c_type, BoundCType)
        assert bound_c_type.adr_space is adr_space
        assert bound_c_type.base_c_type is c_type


class TestCIntegerBase(object):

    CINTEGER_RANGES = [
        (CProgram.char, -0x80, 0x7F),
        (CProgram.unsigned_char, 0x00, 0xFF),
        (CProgram.short, -0x8000, 0x7FFF),
        (CProgram.unsigned_short, 0x0000, 0xFFFF),
        (CProgram.int, -0x80000000, 0x7FFFFFFF),
        (CProgram.unsigned_int, 0x00000000, 0xFFFFFFFF)]

    def test_convert_onPythonType_returnsSameObj(self, bound_int):
        assert bound_int.base_type.convert(22) == 22

    def test_convert_onSameCObjType_returnsCObjsValue(self, bound_int):
        c_obj = bound_int(22)
        assert bound_int.base_type.convert(c_obj) == 22

    def test_convert_onDifferentCScalarSubtype_returnsCObjsValue(self, bound_int):
        c_obj = bound_int(22)
        assert CProgram.char.base_type.convert(c_obj) == 22

    def test_convert_onDifferentCObjType_raisesTypeError(self, bound_int):
        class StrCObj(CObject):
            @classmethod
            def convert(cls, value):
                return value
        different_type_cobj = StrCObj('data')
        with pytest.raises(TypeError):
            bound_int.base_type.convert(different_type_cobj)

    def test_convert_onUninitializedCObjType_raisesVarAccessError(self, bound_int):
        uninitialized_cobj = bound_int()
        with pytest.raises(VarAccessError):
            bound_int.base_type.convert(uninitialized_cobj)

    def test_convert_onDifferntPyObjType_raisesTypeError(self, bound_int):
        with pytest.raises(TypeError):
            bound_int.base_type.convert('invalid-type')

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_convert_onExceedsDefinitionRange_forceToMatch(self, bound_int, ctype, max, min):
        assert ctype.base_type.convert(max) == max
        assert ctype.base_type.convert(max + 1) == min
        assert ctype.base_type.convert(min) == min
        assert ctype.base_type.convert(min - 1) == max
        assert ctype.base_type.convert((max+1)*4 + 123) == 123

    def test_cmp_withPyObj_ok(self, bound_int):
        c_obj = bound_int(1)
        assert c_obj == 1
        assert 0 < c_obj < 2
        assert 1 <= c_obj <= 1
        assert not 0 > c_obj

    def test_cmp_withCObj_ok(self, bound_int):
        c_obj = bound_int(1)
        assert c_obj == bound_int(1)
        assert bound_int(0) < c_obj < bound_int(2)
        assert bound_int(1) <= c_obj <= bound_int(1)
        assert not bound_int(0) > c_obj

    def test_nonZero_onZeroData_returnsFalse(self, bound_int):
        c_obj = bound_int(0)
        assert not c_obj

    def test_nonZero_onNonZeroData_returnsTrue(self, bound_int):
        c_obj = bound_int(3)
        assert c_obj

    def test_sub_withPyObj(self, bound_int):
        c_obj = bound_int(5) - 3
        assert c_obj.val == 2

    def test_sub_withCObj(self, bound_int):
        c_obj = bound_int(5) - bound_int(3)
        assert c_obj.val == 2

    def test_sub_onSignedAndUnsignedCObj_returnsInUnsignedCObj(self, adr_space):
        c_signed_int = CProgram.signed_int(adr_space, 5)
        c_unsigned_int = CProgram.unsigned_int(adr_space, 3)
        c_obj = c_signed_int - c_unsigned_int
        assert isinstance(c_obj, CProgram.unsigned_int.base_type)

    def test_sub_onSmallCObj_widensResult(self, adr_space):
        c_char_plus100 = CProgram.char(adr_space, 100)
        c_char_minus100 = CProgram.char(adr_space, -100)
        c_obj = c_char_minus100 - c_char_plus100
        assert c_obj.val == -200
        assert isinstance(c_obj, CProgram.signed_int.base_type)

    def test_sub_copiesAdrSpace(self, adr_space):
        c_char_5 = CProgram.char(adr_space, 5)
        c_obj = c_char_5 - 3
        assert c_obj.adr_space == adr_space

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, adr_space, ctype, min, max):
        c_obj = ctype(adr_space, min)
        c_obj -= 1
        assert c_obj.val == max

    def test_rsub_withPyObj(self, bound_int):
        c_obj = 5 - bound_int(3)
        assert c_obj.val == 2

    def test_isub_withPyObj(self, bound_int):
        c_obj = bound_int(5)
        c_obj_id = id(c_obj)
        c_obj -= 3
        assert c_obj.val == 2
        assert id(c_obj) == c_obj_id

    def test_isub_withCObj(self, bound_int):
        c_obj = bound_int(5)
        c_obj_id = id(c_obj)
        c_obj -= bound_int(3)
        assert c_obj.val == 2
        assert id(c_obj) == c_obj_id

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, adr_space, ctype, min, max):
        c_obj = ctype(adr_space, min)
        c_obj -= 1
        assert c_obj.val == max

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementMaxValByOne_returnsMinVal(self, adr_space, ctype, min, max):
        c_obj = ctype(adr_space, max)
        c_obj -= -1
        assert c_obj.val == min

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementZeroByMultipleMax_returnsZero(self, adr_space, ctype, min, max):
        c_obj = ctype(adr_space, 0)
        c_obj -= (max + 1) * 4
        assert c_obj.val == 0

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementZeroByMultipleMax_returnsZero(self, adr_space, ctype, min, max):
        c_obj = ctype(adr_space, 0)
        c_obj -= (max + 1) * 4
        assert c_obj.val == 0


class TestCStruct(object):

    @classmethod
    def setup_class(cls):
        class SimpleStruct(CStruct):
            __FIELDS__ = [('a', CProgram.int),
                          ('b', CProgram.short)]
        class NestedStruct(CStruct):
            __FIELDS__ = [('field', CProgram.int),
                          ('inner_struct', CType(SimpleStruct))]
        cls.SimpleStruct = SimpleStruct
        cls.NestedStruct = NestedStruct

    def test_create_createsCObjForEveryField(self, adr_space):
        c_obj = self.SimpleStruct(adr_space)
        assert isinstance(c_obj.a, CProgram.int.base_type)
        assert isinstance(c_obj.b, CProgram.short.base_type)

    def test_create_withoutArgs_createsUninitializedFields(self, adr_space):
        c_obj = self.SimpleStruct(adr_space)
        assert not c_obj.a.initialized
        assert not c_obj.initialized

    def test_create_withPositionaArgs_initializesFieldsByPosition(self, adr_space):
        c_obj = self.SimpleStruct(adr_space, 1, 2)
        assert c_obj.a.val == 1
        assert c_obj.b.val == 2
        assert c_obj.initialized

    def test_create_withKeywordArgs_initializesFieldsByPosition(self, adr_space):
        c_obj = self.SimpleStruct(adr_space, b=1, a=2)
        assert c_obj.a.val == 2
        assert c_obj.b.val == 1
        assert c_obj.initialized

    def test_create_withPartialProvidedArgsOnly_initializesMissingFieldsWith0(self, adr_space):
        c_obj = self.SimpleStruct(adr_space, 1)
        assert c_obj.b.val == 0
        assert c_obj.initialized

    def test_create_onNestedStruct_recursiveCreatesInnerStruct(self, adr_space):
        c_obj = self.NestedStruct(adr_space)
        assert isinstance(c_obj.inner_struct, self.SimpleStruct)

    def test_create_onNestedStructWithPartialProvidedArgs_clearsInnerStructs(self, adr_space):
        c_obj = self.NestedStruct(adr_space, 1)
        assert c_obj.inner_struct.a == 0
        assert c_obj.inner_struct.b == 0

    @pytest.mark.xfail
    def test_create_onNestedStructWithProvidedInnerStructsAsCObj(self, adr_space):
        c_obj = self.NestedStruct(adr_space, 1, self.SimpleStruct(2, 3))
        assert c_obj.field == 1
        assert c_obj.inner_struct.a == 2
        assert c_obj.inner_struct.b == 3

    @pytest.mark.xfail
    def test_repr_onInitialized_returnsDataAsOrderedKeywordInitializers(self):
        c_obj = self.NestedStruct(3, self.SimpleStruct(b=10))
        assert repr(c_obj) == \
               'NestedStruct(field=3, inner_struct=SimpleStruct(a=0, b=10))'


class TestCProgram(object):

    def test_create_onTypedefMemeber_createsBoundCTypes(self):
        class ProgramWithTypeDef(CProgram):
            typedef = CProgram.int
        prog = ProgramWithTypeDef()
        assert isinstance(prog.typedef, BoundCType)
        assert prog.typedef.base_c_type is CProgram.int

    def test_create_onVarMember_createsInstanceVars(self):
        class ProgramWithVar(CProgram):
            def global_vars(self):
                super(ProgramWithVar, self).global_vars()
                self.var = self.int()
        prog = ProgramWithVar()
        assert isinstance(prog.var, prog.int.base_type)

    def test_create_onVarMemberOfCustomTypeDef_createsInstanceVars(self):
        class ProgramWithVar(CProgram):
            typedef = CProgram.int
            def global_vars(self):
                super(ProgramWithVar, self).global_vars()
                self.var = self.typedef()
        prog = ProgramWithVar()
        assert isinstance(prog.var, prog.typedef.base_type)
