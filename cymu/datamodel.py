
class DataModelError(Exception):
    pass


class VarAccessError(DataModelError):
    pass


class InstanceError(DataModelError):
    pass


class AddressSpace(object):
    pass


class CObject(object):
    """
    All C objects are instances of this class
    """

    def __init__(self, adr_space, init_val=None):
        self.__val = None
        self.adr_space = adr_space
        if init_val is not None:
            self.__val = self.convert(init_val)

    @property
    def initialized(self):
        return self.__val is not None

    def get_val(self):
        if self.__val is None:
            raise VarAccessError('variable is not initialized')
        return self.__val

    def set_val(self, new_value):
        self.__val = self.convert(new_value)

    val = property(get_val, set_val)

    @property
    def checked_val(self):
        if self.initialized:
            return self.val
        else:
            raise VarAccessError('variable is not inititialized')

    @classmethod
    def convert(cls, value):
        raise NotImplementedError('This is an abstract base class!')

    def __set__(self, instance, value):
        raise VarAccessError(
            "Cannot change CObjects at runtime (probably you did "
            "'prog.varname = data' instead of 'prog.varname.val = data')")

    def __repr__(self):
        if self.initialized:
            return '{}({!r})'.format(type(self).__name__, self.val)
        else:
            return '{}()'.format(type(self).__name__)


class BoundCType(object):

    def __init__(self, base_c_type, adr_space):
        self.adr_space = adr_space
        self.base_c_type = base_c_type

    def __call__(self, *args, **argv):
        return self.base_c_type(self.adr_space, *args, **argv)

    def __repr__(self):
        return '<bound ' + repr(self.base_type)[1:]

    @property
    def base_type(self):
        return self.base_c_type.base_type


class CType(object):

    def __init__(self, c_type):
        self.base_type = c_type

    def bind(self, adr_space):
        return BoundCType(self, adr_space)

    def __call__(self, adr_space, *args, **kwargs):
        return self.base_type(adr_space, *args, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return BoundCType(self, instance.__adr_space__)


class CIntegerBase(CObject):

    MACHINE_WORD_CTYPES = { True: None, False: None }
    BITS = None   # has to be the number of payload bits (=without sign bit)
    SIGNED = None   # has to be 0 on unsigned type and -1 on signed type

    @classmethod
    def min(self):
        if self.SIGNED:
            return -(1 << (self.BITS-1))
        else:
            return 0

    @classmethod
    def max(self):
        if self.SIGNED:
            return (1 << (self.BITS-1)) - 1
        else:
            return (1 << self.BITS) - 1

    @classmethod
    def convert(cls, val):
        if isinstance(val, CIntegerBase):
            py_obj = val.val
        elif isinstance(val, (int, long)):
            py_obj = val
        else:
            raise TypeError('{!r} cannot be converted to object of class {!r}'
                             .format(val, cls))

        if cls.SIGNED:
            py_obj -= cls.min()
            py_obj &= ((1 << cls.BITS) - 1)
            py_obj += cls.min()
        else:
            py_obj &= ((1 << cls.BITS) - 1)

        py_obj_as_int = int(py_obj)
        if py_obj_as_int == py_obj:
            py_obj = py_obj_as_int

        return py_obj

    def __cmp__(self, value):
        return cmp(self.val, self.convert(value))

    def __nonzero__(self):
        return True if self.val else False

    def __sub__(self, other):
        if isinstance(other, CIntegerBase):
            signed = self.SIGNED and other.SIGNED
        else:
            signed = self.SIGNED
        cobj_type = self.MACHINE_WORD_CTYPES[signed]
        py_obj = cobj_type.convert(self) - cobj_type.convert(other)
        return cobj_type(self.adr_space, py_obj)

    def __isub__(self, other):
        self.val = self - other
        return self

    def __rsub__(self, other):
        ### introduce "instantiate in same addressspace"
        return type(self)(self.adr_space, other) - self


class CStruct(CObject):

    # has to be a list of tuples of names and ctypes, that are describing the
    # fields in this structure
    __FIELDS__ = None

    def __init__(self, adr_space, *args, **argv):
        init_vals = dict(zip((nm for nm, ctype in self.__FIELDS__), args))
        init_vals.update(argv)
        if len(init_vals) != len(args) + len(argv):
            raise TypeError('struct got multiple initialization values for '
                            'single field')
        if len(init_vals) == 0:
            super(CStruct, self).__init__(adr_space)
        else:
            super(CStruct, self).__init__(adr_space, ())
        for attr_name, attr_c_type in self.__FIELDS__:
            if self.initialized:
                field_cobj = attr_c_type(adr_space, init_vals.get(attr_name, 0))
            else:
                field_cobj = attr_c_type(adr_space)
            self.__dict__[attr_name] = field_cobj

    @classmethod
    def convert(cls, val):
        if isinstance(val, CStruct):
            return { nm: getattr(val, nm) for nm, ctype in cls.__FIELDS__ }
        elif isinstance(val, (tuple, dict)):
            return val
        else:
            raise TypeError('{!r} cannot be converted to object of class {!r}'
                            .format(val, cls))

    def __repr__(self):
        if self.initialized:
            return '{}({})'.format(type(self).__name__, ', '.join(
                nm+'='+repr(getattr(self, nm) if isinstance(getattr(self, nm), CStruct) else getattr(self, nm).val)
                for nm, ctype in self.__FIELDS__))
        else:
            return '{}()'.format(type(self).__name__)


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        self.__adr_space__ = AddressSpace()
        self.global_vars()

    def global_vars(self):
        return

    def __repr__(self):
        return "<CProgram>"

    @CType
    class unsigned_int(CIntegerBase):
        BITS = 32
        SIGNED = False

    @CType
    class int(CIntegerBase):
        BITS = 32
        SIGNED = True

    @CType
    class unsigned_short(CIntegerBase):
        BITS = 16
        SIGNED = False

    @CType
    class short(CIntegerBase):
        BITS = 16
        SIGNED = True

    @CType
    class unsigned_char(CIntegerBase):
        BITS = 8
        SIGNED = False

    @CType
    class char(CIntegerBase):
        BITS = 8
        SIGNED = True

    unsigned_int.base_type.MACHINE_WORD_CTYPES = \
    int.base_type.MACHINE_WORD_CTYPES = \
    unsigned_short.base_type.MACHINE_WORD_CTYPES = \
    short.base_type.MACHINE_WORD_CTYPES = \
    unsigned_char.base_type.MACHINE_WORD_CTYPES = \
    char.base_type.MACHINE_WORD_CTYPES = {
        True: int.base_type,
        False: unsigned_int.base_type }

    unsigned_long = unsigned_int
    long = int

    signed_char = char
    signed_short = short
    signed_int = int
    signed_long = long
