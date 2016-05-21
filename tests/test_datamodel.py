import pytest
from cymu import datamodel


class TestData(object):

    class DummyCObj(datamodel.CObject):
        PYTHON_TYPE = str

    def test_getVal_onInitializedInt_returnsInitializedValue(self):
        c_obj = self.DummyCObj('content')
        assert c_obj.val == 'content'

    def test_getVal_onUninitializedInt_raisesVarAccessError(self):
        c_obj = self.DummyCObj()
        with pytest.raises(datamodel.VarAccessError):
            dummy = c_obj.val

    def test_setVal_changesContent(self):
        c_obj = self.DummyCObj()
        c_obj.val = 'content1'
        assert c_obj.val == 'content1'
        c_obj.val = 'content2'
        assert c_obj.val == 'content2'

    def test_isInitialized_onInitializedCObj_returnsTrue(self):
        assert self.DummyCObj('content').is_initialized

    def test_isInitialized_onUninitializedCObj_returnsFalse(self):
        assert not self.DummyCObj().is_initialized

    def test_copy_returnsNewObjWithSameValue(self):
        c_obj = self.DummyCObj('content')
        c_obj_copy = c_obj.copy()
        assert c_obj_copy is not c_obj
        assert c_obj_copy.val == c_obj.val

    def test_copy_onUninitializedCObj_ok(self):
        c_obj = self.DummyCObj()
        c_obj_copy = c_obj.copy()
        assert c_obj_copy is not c_obj
        assert not c_obj_copy.is_initialized

    def test_convert_onPythonType_returnsSameObj(self):
        assert self.DummyCObj.convert('content') == 'content'

    def test_convert_onSameCObjType_returnsCObjsValue(self):
        c_obj = self.DummyCObj('content')
        assert self.DummyCObj.convert(c_obj) == 'content'

    def test_convert_onUnsupportedType_raisesTypeError(self):
        with pytest.raises(TypeError):
            dummy = self.DummyCObj.convert(3)

    def test_getAsMember_returnsDataObj(self):
        class Dummy(object):
            x = self.DummyCObj('content')
        assert Dummy().x.val == 'content'

    def test_setAsMember_raisesVarAccessError(self):
        class Dummy(object):
            x = self.DummyCObj('initial-content')
        dummy = Dummy()
        with pytest.raises(datamodel.VarAccessError):
            dummy.x = self.DummyCObj('another-content')

    def test_cmp_ok(self):
        c_obj = self.DummyCObj('1')
        assert c_obj == '1'
        assert '0' < c_obj < '2'
        assert '1' <= c_obj <= '1'
        assert not '0' > c_obj


class TestProgram(object):

    def test_create_onProgramWithVar_createsCopyOfVar(self):
        class ProgramWithVar(datamodel.CProgram):
            i = datamodel.CInt(11)
        prog = ProgramWithVar()
        assert prog.i.val == ProgramWithVar.i.val
        assert prog.i is not ProgramWithVar.i

    def test_create_onProgramWithTypedef_doNotCopyTypedef(self):
        class ProgramWithTypeDef(datamodel.CProgram):
            i = datamodel.CInt
        prog = ProgramWithTypeDef()
        assert prog.i is ProgramWithTypeDef.i
