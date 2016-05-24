import pytest
from cymu import datamodel


class TestCObject(object):

    def test_initialized_onInitializedCObj_returnsTrue(self):
        assert datamodel.CInt(11).initialized

    def test_initialized_onUninitializedCObj_returnsFalse(self):
        assert not datamodel.CInt().initialized

    def test_checkedVal_onInitializedCObj_returnsVal(self):
        assert datamodel.CInt(11).checked_val == 11

    def test_checkedVal_onUninitializedCObj_raisesVarAccessError(self):
        with pytest.raises(datamodel.VarAccessError):
            _ = datamodel.CInt().checked_val

    def test_copy_returnsNewObjWithSameValue(self):
        c_obj = datamodel.CInt(11)
        c_obj_copy = c_obj.copy()
        assert c_obj_copy is not c_obj
        assert c_obj_copy.val == c_obj.val

    def test_copy_onUninitializedCObj_ok(self):
        c_obj = datamodel.CInt()
        c_obj_copy = c_obj.copy()
        assert c_obj_copy is not c_obj
        assert not c_obj_copy.initialized

    def test_convert_onPythonType_returnsSameObj(self):
        assert datamodel.CInt.convert(22) == 22

    def test_convert_onSameCObjType_returnsCObjsValue(self):
        c_obj = datamodel.CInt(22)
        assert datamodel.CInt.convert(c_obj) == 22

    def test_convert_onDifferentCObjType_raisesTypeError(self):
        class StrCObj(datamodel.CObject):
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

    def test_getDescriptor_returnsAssignedCObjectInContainingDict(self):
        c_obj_def = datamodel.CInt(11)
        c_obj_val = datamodel.CInt(22)
        class Container(dict):
            c_obj = c_obj_def
        container = Container({c_obj_def: c_obj_val})
        assert container.c_obj is c_obj_val

    def test_getDescriptor_onUninstanciatedContaingDict_returnsSelf(self):
        c_obj_def = datamodel.CInt(11)
        class Container(dict):
            c_obj = c_obj_def
        assert Container.c_obj is c_obj_def

    def test_setDescriptor_replaceValInCObjOfContainingDictWithConvertedVal(self):
        class DummyConvertCInt(datamodel.CInt):
            def convert(cls, value):
                return 99
        c_obj_def = DummyConvertCInt(11)
        c_obj_val_old = DummyConvertCInt(22)
        c_obj_val_new = datamodel.CInt()
        class Container(dict):
            c_obj = c_obj_def
        container = Container({c_obj_def: c_obj_val_old})
        container.c_obj = c_obj_val_new
        assert container[c_obj_def] is c_obj_val_old
        assert container[c_obj_def].val == 99

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

    def test_isub_withPyObj(self):
        c_obj = datamodel.CInt(5)
        c_obj -= 3
        assert c_obj.val == 2

    def test_isub_withCObj(self):
        c_obj = datamodel.CInt(5)
        c_obj -= datamodel.CInt(3)
        assert c_obj.val == 2

    def test_subAssign_withCObj(self):
        c_obj = datamodel.CInt(5)
        c_obj -= datamodel.CInt(3)
        assert c_obj.val == 2

    def test_sub_withPyObj(self):
        c_obj = datamodel.CInt(5) - 3
        assert c_obj.val == 2

    def test_sub_withCObj(self):
        c_obj = datamodel.CInt(5) - datamodel.CInt(3)
        assert c_obj.val == 2

    def test_rsub_withPyObj(self):
        c_obj = 5 - datamodel.CInt(3)
        assert c_obj.val == 2


class TestCProgram(object):

    def test_create_onProgramWithTypedef_doNotCopyTypedef(self):
        class ProgramWithTypeDef(datamodel.CProgram):
            typedef = datamodel.CInt
        prog = ProgramWithTypeDef()
        assert prog.typedef is datamodel.CInt

    def test_create_onProgramWithVar_createsCopyOfVar(self):
        var_def = datamodel.CInt(11)
        class ProgramWithVar(datamodel.CProgram):
            var = var_def
        prog = ProgramWithVar()
        assert isinstance(prog[var_def], datamodel.CInt)
        assert prog[var_def] is not var_def
        assert prog[var_def].val == 11
