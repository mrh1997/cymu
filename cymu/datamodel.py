
class DataModelError(Exception):
    pass


class VarAccessError(DataModelError):
    pass


class InstanceError(DataModelError):
    pass


class AddressSpace(object):
    pass


class CObj(object):
    """
    All C objects are instances of this class
    """

    def __init__(self, ctype, adr_space, init_val=None):
        self.ctype = ctype
        self.adr_space = adr_space
        self.__val = None
        if init_val is not None:
            self.__val = self.ctype.convert(init_val)

    @property
    def initialized(self):
        return self.__val is not None

    def get_val(self):
        if self.__val is None:
            raise VarAccessError('variable is not initialized')
        return self.__val

    def set_val(self, new_value):
        self.__val = self.ctype.convert(new_value)

    val = property(get_val, set_val)

    @property
    def checked_val(self):
        if self.initialized:
            return self.val
        else:
            raise VarAccessError('variable is not inititialized')

    def __set__(self, instance, value):
        raise VarAccessError(
            "Cannot change CObjects at runtime (probably you did "
            "'prog.varname = data' instead of 'prog.varname.val = data')")

    def __repr__(self):
        if self.initialized:
            return '{0.ctype.name}({0.val!r})'.format(self)
        else:
            return '{0.ctype.name}()'.format(self)


class BoundCType(object):

    def __init__(self, base_ctype, adr_space):
        self.adr_space = adr_space
        self.base_ctype = base_ctype

    def __call__(self, *args, **argv):
        return self.base_ctype(self.adr_space, *args, **argv)

    def __repr__(self):
        return '<bound ' + repr(self.base_ctype)[1:]

    @property
    def cobj_type(self):
        return self.base_ctype.COBJ_TYPE

    def __getattr__(self, item):
        return getattr(self.base_ctype, item)


class CType(object):

    COBJ_TYPE = None

    def __init__(self, name):
        super(CType, self).__init__()
        self.name = name

    def bind(self, adr_space):
        return BoundCType(self, adr_space)

    def __call__(self, adr_space, *args, **kwargs):
        return self.COBJ_TYPE(self, adr_space, *args, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return BoundCType(self, instance.__adr_space__)

    def __repr__(self):
        return '<CType {!r}>'.format(self.name)

    def convert(self, value):
        raise NotImplementedError('This is an abstract base class!')


class IntCObj(CObj):

    def __cmp__(self, value):
        return cmp(self.val, self.ctype.convert(value))

    def __nonzero__(self):
        return True if self.val else False

    def __sub__(self, other):
        cobj_type = self.ctype.common_ctype(other)
        pyobj = cobj_type.convert(self) - cobj_type.convert(other)
        return cobj_type(self.adr_space, pyobj)

    def __isub__(self, other):
        self.val = self - other
        return self

    def __rsub__(self, other):
        ### introduce "instantiate in same addressspace"
        ctype = self.ctype.common_ctype(other)
        return ctype(self.adr_space, other) - self


class IntCType(CType):

    COBJ_TYPE = IntCObj

    def __init__(self, name, bits, signed, machine_words=None):
        super(IntCType, self).__init__(name)
        self.bits = bits
        self.signed = signed
        self.machine_words = machine_words

    def min(self):
        if self.signed:
            return -(1 << (self.bits - 1))
        else:
            return 0

    def max(self):
        if self.signed:
            return (1 << (self.bits - 1)) - 1
        else:
            return (1 << self.bits) - 1

    def convert(self, val):
        if isinstance(val, IntCObj):
            py_obj = val.val
        elif isinstance(val, (int, long)):
            py_obj = val
        else:
            raise TypeError('{!r} cannot be converted to object of class {!r}'
                            .format(val, self))

        if self.signed:
            py_obj -= self.min()
            py_obj &= ((1 << self.bits) - 1)
            py_obj += self.min()
        else:
            py_obj &= ((1 << self.bits) - 1)

        py_obj_as_int = int(py_obj)
        if py_obj_as_int == py_obj:
            py_obj = py_obj_as_int

        return py_obj

    def common_ctype(self, other):
        if isinstance(other, self.COBJ_TYPE):
            signed = self.signed and other.ctype.signed
        else:
            signed = self.signed
        cobj_type = self.machine_words[signed]
        return cobj_type


class StructCObj(CObj):

    def __init__(self, ctype, adr_space, *args, **argv):
        init_vals = dict(zip((nm for nm, ctype in ctype.fields), args))
        init_vals.update(argv)
        if len(init_vals) != len(args) + len(argv):
            raise TypeError('struct got multiple initialization values for '
                            'single field')
        if len(init_vals) == 0:
            super(StructCObj, self).__init__(ctype, adr_space)
        else:
            super(StructCObj, self).__init__(ctype, adr_space, ())
        for attr_name, attr_c_type in ctype.fields:
            if self.initialized:
                field_cobj = attr_c_type(adr_space, init_vals.get(attr_name, 0))
            else:
                field_cobj = attr_c_type(adr_space)
            self.__dict__[attr_name] = field_cobj

    def __repr__(self):
        if self.initialized:
            return '{}({})'.format(type(self).__name__, ', '.join(
                nm+'='+repr(getattr(self, nm) if isinstance(getattr(self, nm), StructCObj) else getattr(self, nm).val)
                for nm, ctype in self.ctype.fields))
        else:
            return '{}()'.format(type(self).__name__)


class StructCType(CType):

    COBJ_TYPE = StructCObj

    def __init__(self, name, fields):
        super(StructCType, self).__init__(name)
        self.fields = fields

    def convert(self, val):
        if isinstance(val, StructCObj):
            return {nm: getattr(val, nm) for nm, ctype in self.__FIELDS__}
        elif isinstance(val, (tuple, dict)):
            return val
        else:
            raise TypeError('{!r} cannot be converted to object of class {!r}'
                            .format(val, self))


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        self.__adr_space__ = AddressSpace()
        self.global_vars()

    def global_vars(self):
        return

    def __repr__(self):
        return "<CProgram>"

    int = IntCType('int', bits=32, signed=True)
    unsigned_int = IntCType('unsigned_int', bits=32, signed=False)
    MACHINE_WORDS = int.machine_words = unsigned_int.machine_words = {
        True: int,
        False: unsigned_int }

    unsigned_long = IntCType('unsigned_long', bits=32, signed=False,
                             machine_words=MACHINE_WORDS)
    long = IntCType('long', bits=32, signed=True,
                    machine_words=MACHINE_WORDS)
    unsigned_short = IntCType('unsigned_short', bits=16, signed=False,
                              machine_words=MACHINE_WORDS)
    short = IntCType('short', bits=16, signed=True,
                     machine_words=MACHINE_WORDS)
    unsigned_char = IntCType('unsigned_char', bits=8, signed=False,
                             machine_words=MACHINE_WORDS)
    char = IntCType('char', bits=8, signed=True,
                    machine_words=MACHINE_WORDS)
