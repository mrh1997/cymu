import pytest

from cymu.datamodel import CProgram, CData, CStruct, AddressSpace, BoundCType, \
    InstanceError, VarAccessError


@pytest.fixture
def adr_space():
    return AddressSpace()


class TestCData(object):

    def test_init_withPyObj_ok(self):
        c_obj = CProgram.int(11)
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_init_withCObj_ok(self):
        c_obj = CProgram.int(CProgram.int(11))
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_bind_returnsBoundCData(self, adr_space):
        bound_ctype = CProgram.int.bind(adr_space)
        assert isinstance(bound_ctype, BoundCType)
        assert bound_ctype.base_type == CProgram.int
        assert bound_ctype.adr_space == adr_space

    def test_createInstance_onUninitializedCObj_returnsUninitializedClone(self, adr_space):
        c_obj = CProgram.int()
        c_obj_inst = c_obj.create_instance(adr_space)
        assert c_obj_inst is not c_obj
        assert not c_obj_inst.initialized

    def test_createInstance_onInitializedCObj_returnsInitializedClone(self, adr_space):
        c_obj = CProgram.int(11)
        c_obj_inst = c_obj.create_instance(adr_space)
        assert c_obj_inst is not c_obj
        assert c_obj_inst.val == c_obj.val

    def test_createInstance_alreadyInstantiatedCObj_raisesInstanceError(self, adr_space):
        c_obj_inst = CProgram.int().create_instance(adr_space)
        with pytest.raises(InstanceError):
            c_obj_inst.create_instance(adr_space)

    def test_instantiated_onUninstanciatedObj_returnsFalse(self):
        c_obj = CProgram.int()
        assert not c_obj.instantiated

    def test_instantiated_onInstanciatedObj_returnsTrue(self, adr_space):
        c_obj_inst = CProgram.int().create_instance(adr_space)
        assert c_obj_inst.instantiated

    def test_setVal_onUninstanced_raisesInstanceErrorr(self):
        c_obj = CProgram.int()
        with pytest.raises(InstanceError):
            c_obj.val = 11

    def test_setVal_onInstantiatedWithPyObj_ok(self, adr_space):
        c_obj = CProgram.int().create_instance(adr_space)
        c_obj.val = 11
        assert c_obj.val == 11

    def test_setVal_onInstantiatedWithCObj_ok(self, adr_space):
        c_obj = CProgram.int().create_instance(adr_space)
        c_obj.val = CProgram.int(11)
        assert c_obj.val == 11

    def test_initialized_onInitializedCObj_returnsTrue(self):
        assert CProgram.int(11).initialized

    def test_initialized_onUninitializedCObj_returnsFalse(self):
        assert not CProgram.int().initialized

    def test_checkedVal_onInitializedCObj_returnsVal(self):
        assert CProgram.int(11).checked_val == 11

    def test_checkedVal_onUninitializedCObj_raisesVarAccessError(self):
        with pytest.raises(VarAccessError):
            _ = CProgram.int().checked_val

    def test_setDescriptor_raisesVarAccessError(self):
        class Container(object):
            var = CProgram.int()
        container = Container()
        with pytest.raises(VarAccessError):
            container.var = 3

    def test_repr(self):
        c_obj = CProgram.int()
        assert repr(c_obj) == 'int()'

    def test_repr_onInitializedObj(self):
        c_obj = CProgram.int(3)
        assert repr(c_obj) == 'int(3)'

    def test_repr_onInstantiatedObj(self, adr_space):
        c_obj_inst = CProgram.int().create_instance(adr_space)
        assert repr(c_obj_inst) == '<int() instance>'


class TestBoundCType(object):

    @pytest.fixture()
    def bound_int(selfadr_space):
        return BoundCType(CProgram.int, adr_space)

    def test_call_returnsInstanceCObj(self, bound_int):
        cobj = bound_int()
        assert isinstance(cobj, CProgram.int)
        assert cobj.instantiated

    def test_call_withPositionalParams_forwardsParamsToBaseType(self, bound_int):
        cobj = bound_int(3)
        assert cobj.val == 3

    def test_call_withKeywordParams_forwardsParamsToBaseType(self, bound_int):
        cobj = bound_int(init_val=3)
        assert cobj.val == 3

    def test_repr(self, bound_int):
        assert repr(bound_int) == "<bound class 'cymu.datamodel.int'>"



class TestCIntegerBase(object):

    CINTEGER_RANGES = [
        (CProgram.char, -0x80, 0x7F),
        (CProgram.unsigned_char, 0x00, 0xFF),
        (CProgram.short, -0x8000, 0x7FFF),
        (CProgram.unsigned_short, 0x0000, 0xFFFF),
        (CProgram.int, -0x80000000, 0x7FFFFFFF),
        (CProgram.unsigned_int, 0x00000000, 0xFFFFFFFF)]

    def test_convert_onPythonType_returnsSameObj(self):
        assert CProgram.int.convert(22) == 22

    def test_convert_onSameCObjType_returnsCObjsValue(self):
        c_obj = CProgram.int(22)
        assert CProgram.int.convert(c_obj) == 22

    def test_convert_onDifferentCScalarSubtype_returnsCObjsValue(self):
        c_obj = CProgram.int(22)
        assert CProgram.char.convert(c_obj) == 22

    def test_convert_onDifferentCObjType_raisesTypeError(self):
        class StrCObj(CData):
            @classmethod
            def convert(cls, value):
                return value
        different_type_cobj = StrCObj('data')
        with pytest.raises(TypeError):
            CProgram.int.convert(different_type_cobj)

    def test_convert_onUninitializedCObjType_raisesVarAccessError(self):
        uninitialized_cobj = CProgram.int()
        with pytest.raises(VarAccessError):
            CProgram.int.convert(uninitialized_cobj)

    def test_convert_onDifferntPyObjType_raisesTypeError(self):
        with pytest.raises(TypeError):
            CProgram.int.convert('invalid-type')

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_convert_onExceedsDefinitionRange_forceToMatch(self, ctype, max, min):
        assert ctype.convert(max) == max
        assert ctype.convert(max + 1) == min
        assert ctype.convert(min) == min
        assert ctype.convert(min - 1) == max
        assert ctype.convert((max+1)*4 + 123) == 123

    def test_cmp_withPyObj_ok(self):
        c_obj = CProgram.int(1)
        assert c_obj == 1
        assert 0 < c_obj < 2
        assert 1 <= c_obj <= 1
        assert not 0 > c_obj

    def test_cmp_withCObj_ok(self):
        c_obj = CProgram.int(1)
        assert c_obj == CProgram.int(1)
        assert CProgram.int(0) < c_obj < CProgram.int(2)
        assert CProgram.int(1) <= c_obj <= CProgram.int(1)
        assert not CProgram.int(0) > c_obj

    def test_nonZero_onZeroData_returnsFalse(self):
        c_obj = CProgram.int(0)
        assert not c_obj

    def test_nonZero_onNonZeroData_returnsTrue(self):
        c_obj = CProgram.int(3)
        assert c_obj

    def test_sub_withPyObj(self):
        c_obj = CProgram.int(5) - 3
        assert c_obj.val == 2

    def test_sub_withCObj(self):
        c_obj = CProgram.int(5) - CProgram.int(3)
        assert c_obj.val == 2

    def test_sub_onSignedAndUnsignedCObj_returnsInUnsignedCObj(self):
        c_obj = CProgram.signed_int(5) - CProgram.unsigned_int(3)
        assert isinstance(c_obj, CProgram.unsigned_int)

    def test_sub_onSmallCObj_widensResult(self):
        c_obj = CProgram.char(-100) - CProgram.char(100)
        assert c_obj.val == -200
        assert isinstance(c_obj, CProgram.signed_int)

    def test_sub_onInstantiatedCObj_returnsInstantiatedCObj(self, adr_space):
        c_obj = CProgram.char(5).create_instance(adr_space) - 3
        assert c_obj.instantiated

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, ctype, min, max):
        c_obj = ctype(min).create_instance(AddressSpace())
        c_obj -= 1
        assert c_obj.val == max

    def test_rsub_withPyObj(self):
        c_obj = 5 - CProgram.int(3)
        assert c_obj.val == 2

    def test_isub_onNonInstanceCObj_raisesInstanceError(self):
        c_obj = CProgram.int(5)
        with pytest.raises(InstanceError):
            c_obj -= 3

    def test_isub_withPyObj(self, adr_space):
        c_obj = CProgram.int(5).create_instance((adr_space))
        c_obj_id = id(c_obj)
        c_obj -= 3
        assert c_obj.val == 2
        assert id(c_obj) == c_obj_id

    def test_isub_withCObj(self, adr_space):
        c_obj = CProgram.int(5).create_instance(adr_space)
        c_obj_id = id(c_obj)
        c_obj -= CProgram.int(3).create_instance(adr_space)
        assert c_obj.val == 2
        assert id(c_obj) == c_obj_id

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementMinValByOne_returnsMaxVal(self, ctype, min, max):
        c_obj = ctype(min).create_instance(AddressSpace())
        c_obj -= 1
        assert c_obj.val == max

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementMaxValByOne_returnsMinVal(self, ctype, min, max):
        c_obj = ctype(max).create_instance(AddressSpace())
        c_obj -= -1
        assert c_obj.val == min

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onDecrementZeroByMultipleMax_returnsZero(self, ctype, min, max):
        c_obj = ctype(0).create_instance(AddressSpace())
        c_obj -= (max + 1) * 4
        assert c_obj.val == 0

    @pytest.mark.parametrize(('ctype', 'min', 'max'), CINTEGER_RANGES)
    def test_isub_onIncrementZeroByMultipleMax_returnsZero(self, ctype, min, max):
        c_obj = ctype(0).create_instance(AddressSpace())
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
                          ('inner_struct', SimpleStruct)]
        cls.SimpleStruct = SimpleStruct
        cls.NestedStruct = NestedStruct

    def test_create_createsCObjForEveryField(self):
        c_obj = self.SimpleStruct()
        assert isinstance(c_obj.a, CProgram.int)
        assert isinstance(c_obj.b, CProgram.short)

    def test_create_withoutArgs_createsUninitializedFields(self):
        c_obj = self.SimpleStruct()
        assert not c_obj.a.initialized
        assert not c_obj.initialized

    def test_create_withPositionaArgs_initializesFieldsByPosition(self):
        c_obj = self.SimpleStruct(1, 2)
        assert c_obj.a.val == 1
        assert c_obj.b.val == 2
        assert c_obj.initialized

    def test_create_withKeywordArgs_initializesFieldsByPosition(self):
        c_obj = self.SimpleStruct(b=1, a=2)
        assert c_obj.a.val == 2
        assert c_obj.b.val == 1
        assert c_obj.initialized

    def test_create_withPartialProvidedArgsOnly_initializesMissingFieldsWith0(self):
        c_obj = self.SimpleStruct(1)
        assert c_obj.b.val == 0
        assert c_obj.initialized

    def test_create_onNestedStruct_recursiveCreatesInnerStruct(self):
        c_obj = self.NestedStruct()
        assert isinstance(c_obj.inner_struct, self.SimpleStruct)

    def test_create_onNestedStructWithPartialProvidedArgs_clearsInnerStructs(self):
        c_obj = self.NestedStruct(1)
        assert c_obj.inner_struct.a == 0
        assert c_obj.inner_struct.b == 0

    @pytest.mark.xfail
    def test_create_onNestedStructWithProvidedInnerStructsAsCObj(self):
        c_obj = self.NestedStruct(1, self.SimpleStruct(2, 3))
        assert c_obj.field == 1
        assert c_obj.inner_struct.a == 2
        assert c_obj.inner_struct.b == 3

    def test_createInstance_createsInstanceOfFieldsRecursivly(self, adr_space):
        c_obj = self.NestedStruct()
        c_obj_inst = c_obj.create_instance(adr_space)
        assert c_obj_inst.field.instantiated
        assert c_obj_inst.inner_struct.a.instantiated
        assert c_obj_inst.inner_struct.b.instantiated

    def test_createInstance_copiesInitVals(self, adr_space):
        c_obj = self.SimpleStruct(2)
        c_obj_inst = c_obj.create_instance(adr_space)
        assert c_obj_inst.a == 2

    def test_instiantiated_onInstantiatedStruct_returnTrue(self, adr_space):
        c_obj_inst = self.SimpleStruct().create_instance(adr_space)
        assert c_obj_inst.instantiated

    def test_repr_onUninitialized_returnsEmptyBrackets(self):
        assert repr(self.SimpleStruct()) == 'SimpleStruct()'

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
        assert prog.typedef.base_type == CProgram.int

    def test_create_onVarMember_createsInstanceVars(self):
        class ProgramWithVar(CProgram):
            var = CProgram.int()
        prog = ProgramWithVar()
        assert isinstance(prog.var, CProgram.int)
        assert prog.var.instantiated
