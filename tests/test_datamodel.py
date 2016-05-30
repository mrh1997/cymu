import pytest
from cymu import datamodel


@pytest.fixture
def bound_cint():
    adr_space = datamodel.AddressSpace()
    return datamodel.CInt.bind(adr_space)


class TestCData(object):

    def test_init_withPyObj_ok(self):
        c_obj = datamodel.CInt(11)
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_init_withCObj_ok(self):
        c_obj = datamodel.CInt(datamodel.CInt(11))
        assert isinstance(c_obj.val, int)
        assert c_obj.val == 11

    def test_bind_returnsBoundCData(self):
        adr_space = datamodel.AddressSpace()
        bound_ctype = datamodel.CInt.bind(adr_space)
        assert isinstance(bound_ctype, datamodel.BoundCType)
        assert bound_ctype.base_type == datamodel.CInt
        assert bound_ctype.adr_space == adr_space

    def test_createInstance_onUninitializedCObj_returnsUninitializedClone(self):
        c_obj = datamodel.CInt()
        c_obj_inst = c_obj.create_instance(datamodel.AddressSpace())
        assert c_obj_inst is not c_obj
        assert not c_obj_inst.initialized

    def test_createInstance_onInitializedCObj_returnsInitializedClone(self):
        c_obj = datamodel.CInt(11)
        c_obj_inst = c_obj.create_instance(datamodel.AddressSpace())
        assert c_obj_inst is not c_obj
        assert c_obj_inst.val == c_obj.val

    def test_createInstance_alreadyInstantiatedCObj_raisesInstanceError(self):
        adr_space = datamodel.AddressSpace()
        c_obj_inst = datamodel.CInt().create_instance(adr_space)
        with pytest.raises(datamodel.InstanceError):
            c_obj_inst.create_instance(adr_space)

    def test_instantiated_onUninstanciatedObj_returnsFalse(self):
        c_obj = datamodel.CInt()
        assert not c_obj.instantiated

    def test_instantiated_onInstanciatedObj_returnsTrue(self):
        c_obj_inst = datamodel.CInt().create_instance(datamodel.AddressSpace())
        assert c_obj_inst.instantiated

    def test_setVal_onUninstanced_raisesInstanceErrorr(self):
        c_obj = datamodel.CInt()
        with pytest.raises(datamodel.InstanceError):
            c_obj.val = 11

    def test_setVal_onInstantiatedWithPyObj_ok(self):
        c_obj = datamodel.CInt().create_instance(datamodel.AddressSpace())
        c_obj.val = 11
        assert c_obj.val == 11

    def test_setVal_onInstantiatedWithCObj_ok(self):
        c_obj = datamodel.CInt().create_instance(datamodel.AddressSpace())
        c_obj.val = datamodel.CInt(11)
        assert c_obj.val == 11

    def test_initialized_onInitializedCObj_returnsTrue(self):
        assert datamodel.CInt(11).initialized

    def test_initialized_onUninitializedCObj_returnsFalse(self):
        assert not datamodel.CInt().initialized

    def test_checkedVal_onInitializedCObj_returnsVal(self):
        assert datamodel.CInt(11).checked_val == 11

    def test_checkedVal_onUninitializedCObj_raisesVarAccessError(self):
        with pytest.raises(datamodel.VarAccessError):
            _ = datamodel.CInt().checked_val

    def test_convert_onPythonType_returnsSameObj(self):
        assert datamodel.CInt.convert(22) == 22

    def test_convert_onSameCObjType_returnsCObjsValue(self):
        c_obj = datamodel.CInt(22)
        assert datamodel.CInt.convert(c_obj) == 22

    def test_convert_onDifferentCObjType_raisesTypeError(self):
        class StrCObj(datamodel.CData):
            PYTHON_TYPE = str
        different_type_cobj = StrCObj('data')
        with pytest.raises(TypeError):
            datamodel.CInt.convert(different_type_cobj)

    def test_convert_onUninitializedCObjType_raisesVarAccessError(self):
        uninitialized_cobj = datamodel.CInt()
        with pytest.raises(datamodel.VarAccessError):
            datamodel.CInt.convert(uninitialized_cobj)

    def test_convert_onDifferntPyObjType_raisesTypeError(self):
        with pytest.raises(TypeError):
            datamodel.CInt.convert('invalid-type')

    def test_setDescriptor_raisesVarAccessError(self):
        class Container(object):
            var = datamodel.CInt()
        container = Container()
        with pytest.raises(datamodel.VarAccessError):
            container.var = 3

    def test_repr(self):
        c_obj = datamodel.CInt()
        assert repr(c_obj) == 'CInt()'

    def test_repr_onInitializedObj(self):
        c_obj = datamodel.CInt(3)
        assert repr(c_obj) == 'CInt(3)'

    def test_repr_onInstantiatedObj(self, bound_cint):
        c_obj_inst = bound_cint()
        assert repr(c_obj_inst) == '<CInt() instance>'


class TestBoundCType(object):

    def test_call_returnsInstanceCObj(self, bound_cint):
        cobj = bound_cint()
        assert isinstance(cobj, datamodel.CInt)
        assert cobj.instantiated

    def test_call_withPositionalParams_forwardsParamsToBaseType(self, bound_cint):
        cobj = bound_cint(3)
        assert cobj.val == 3

    def test_call_withKeywordParams_forwardsParamsToBaseType(self, bound_cint):
        cobj = bound_cint(init_val=3)
        assert cobj.val == 3

    def test_repr(self, bound_cint):
        assert repr(bound_cint) == "<bound class 'cymu.datamodel.CInt'>"



class TestCInt(object):

    def test_cmp_withPyObj_ok(self):
        c_obj = datamodel.CInt(1)
        assert c_obj == 1
        assert 0 < c_obj < 2
        assert 1 <= c_obj <= 1
        assert not 0 > c_obj

    def test_cmp_withCObj_ok(self):
        c_obj = datamodel.CInt(1)
        assert c_obj == datamodel.CInt(1)
        assert datamodel.CInt(0) < c_obj < datamodel.CInt(2)
        assert datamodel.CInt(1) <= c_obj <= datamodel.CInt(1)
        assert not datamodel.CInt(0) > c_obj

    def test_nonZero_onZeroData_returnsFalse(self):
        c_obj = datamodel.CInt(0)
        assert not c_obj

    def test_nonZero_onNonZeroData_returnsTrue(self):
        c_obj = datamodel.CInt(3)
        assert c_obj

    def test_isub_onNonInstanceCObj_raisesInstanceError(self):
        c_obj = datamodel.CInt(5)
        with pytest.raises(datamodel.InstanceError):
            c_obj -= 3

    def test_isub_withPyObj(self, bound_cint):
        c_obj = bound_cint(5)
        c_obj -= 3
        assert c_obj.val == 2

    def test_isub_withCObj(self, bound_cint):
        c_obj = bound_cint(5)
        c_obj -= bound_cint(3)
        assert c_obj.val == 2

    def test_sub_withPyObj(self):
        c_obj = datamodel.CInt(5) - 3
        assert c_obj.val == 2

    def test_sub_withCObj(self):
        c_obj = datamodel.CInt(5) - datamodel.CInt(3)
        assert c_obj.val == 2

    def test_sub_onInstanceObj_returnsInstanceObj(self, bound_cint):
        c_obj = bound_cint(4) - 3
        assert c_obj.instantiated

    def test_rsub_withPyObj(self):
        c_obj = 5 - datamodel.CInt(3)
        assert c_obj.val == 2


class TestCProgram(object):

    def test_create_onTypedefMemeber_createsBoundCTypes(self):
        class ProgramWithTypeDef(datamodel.CProgram):
            typedef = datamodel.CInt
        prog = ProgramWithTypeDef()
        assert isinstance(prog.typedef, datamodel.BoundCType)
        assert prog.typedef.base_type == datamodel.CInt

    def test_create_onVarMember_createsInstanceVars(self):
        class ProgramWithVar(datamodel.CProgram):
            var = datamodel.CInt()
        prog = ProgramWithVar()
        assert isinstance(prog.var, datamodel.CInt)
        assert prog.var.instantiated
