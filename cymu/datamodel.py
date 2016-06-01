
class DataModelError(Exception):
    pass


class VarAccessError(DataModelError):
    pass


class InstanceError(DataModelError):
    pass


class AddressSpace(object):
    pass


class CData(object):
    """
    All C objects are instances of this class
    """

    def __init__(self, init_val=None):
        self.__val = None
        self.adr_space = None
        if init_val is not None:
            self.__val = self.convert(init_val)

    @classmethod
    def bind(cls, adr_space):
        return BoundCType(cls, adr_space)

    @property
    def initialized(self):
        return self.__val is not None

    def get_val(self):
        if self.__val is None:
            raise VarAccessError('variable is not initialized')
        return self.__val

    def set_val(self, new_value):
        if not self.instantiated:
            raise InstanceError('can only set value if corresponding '
                                'CData object was instantiated')
        self.__val = self.convert(new_value)

    val = property(get_val, set_val)

    @property
    def checked_val(self):
        if self.initialized:
            return self.val
        else:
            raise VarAccessError('variable is not inititialized')

    def create_instance(self, address_space):
        if self.adr_space is not None:
            raise InstanceError('Cannot create an instance fromn an already '
                                'instantiated CData object')
        else:
            inst_cobj = type(self)(self.__val)
            inst_cobj.adr_space = address_space
            return inst_cobj

    @property
    def instantiated(self):
        return self.adr_space is not None

    @classmethod
    def convert(cls, value):
        raise NotImplementedError('This is an abstract base class!')

    def __set__(self, instance, value):
        raise VarAccessError(
            "Cannot change CObjects at runtime (probably you did "
            "'prog.varname = data' instead of 'prog.varname.val = data')")

    def __repr__(self):
        if self.initialized:
            result = '{}({!r})'.format(type(self).__name__, self.val)
        else:
            result = '{}()'.format(type(self).__name__)
        if self.instantiated:
            return '<'+result+' instance>'
        else:
            return result


class BoundCType(object):

    def __init__(self, base_type, adr_space):
        self.base_type = base_type
        self.adr_space = adr_space

    def __call__(self, *args, **argv):
        c_obj = self.base_type(*args, **argv)
        return c_obj.create_instance(self.adr_space)

    def __repr__(self):
        return '<bound ' + repr(self.base_type)[1:]


class CIntegerBase(CData):

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
        mword_ctype = self.MACHINE_WORD_CTYPES[signed]
        py_obj = mword_ctype.convert(self) - mword_ctype.convert(other)
        c_obj = mword_ctype(py_obj)
        if self.instantiated:
            return c_obj.create_instance(self.adr_space)
        else:
            return c_obj

    def __isub__(self, other):
        self.val = self - other
        return self

    def __rsub__(self, other):
        return type(self)(other) - self


class CStruct(CData):

    # has to be a list of tuples of names and ctypes, that are describing the
    # fields in this structure
    __FIELDS__ = None

    def __init__(self, *args, **argv):
        init_vals = dict(zip((nm for nm, ctype in self.__FIELDS__), args))
        init_vals.update(argv)
        if len(init_vals) != len(args) + len(argv):
            raise TypeError('struct got multiple initialization values for '
                            'single field')
        if len(init_vals) == 0:
            super(CStruct, self).__init__()
        else:
            super(CStruct, self).__init__(())
        for attrname, attrtype in self.__FIELDS__:
            if self.initialized:
                field_cobj = attrtype(init_vals.get(attrname, 0))
            else:
                field_cobj = attrtype()
            self.__dict__[attrname] = field_cobj

    @classmethod
    def convert(cls, val):
        if isinstance(val, CStruct):
            return { nm: getattr(val, nm) for nm, ctype in cls.__FIELDS__ }
        elif isinstance(val, (tuple, dict)):
            return val
        else:
            raise TypeError('{!r} cannot be converted to object of class {!r}'
                            .format(val, cls))

    def create_instance(self, address_space):
        struct_inst = type(self)()
        struct_inst.adr_space = address_space
        if self.adr_space is not None:
            raise InstanceError('Cannot create an instance fromn an already '
                                'instantiated CData object')
        for attrname, attrtype in self.__FIELDS__:
            field_inst = self.__dict__[attrname].create_instance(address_space)
            struct_inst.__dict__[attrname] = field_inst
        return struct_inst

    def __repr__(self):
        if self.initialized:
            result = '{}({})'.format(type(self).__name__, ', '.join(
                nm+'='+repr(getattr(self, nm) if isinstance(getattr(self, nm), CStruct) else getattr(self, nm).val)
                for nm, ctype in self.__FIELDS__))
        else:
            result = '{}()'.format(type(self).__name__)
        if self.instantiated:
            return '<'+result+' instance>'
        else:
            return result


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        adr_space = AddressSpace()
        for attrname in dir(self):
            attr = getattr(type(self), attrname)
            if isinstance(attr, type):
                if issubclass(attr, CData):
                    self.__dict__[attrname] = attr.bind(adr_space)
            elif isinstance(attr, CData):
                self.__dict__[attrname] = attr.create_instance(adr_space)

    def __repr__(self):
        return "<CProgram>"

    class unsigned_int(CIntegerBase):
        BITS = 32
        SIGNED = False

    class int(CIntegerBase):
        BITS = 32
        SIGNED = True

    class unsigned_short(CIntegerBase):
        BITS = 16
        SIGNED = False

    class short(CIntegerBase):
        BITS = 16
        SIGNED = True

    class unsigned_char(CIntegerBase):
        BITS = 8
        SIGNED = False

    class char(CIntegerBase):
        BITS = 8
        SIGNED = True

    unsigned_int.MACHINE_WORD_CTYPES = \
    int.MACHINE_WORD_CTYPES = \
    unsigned_short.MACHINE_WORD_CTYPES = \
    short.MACHINE_WORD_CTYPES = \
    unsigned_char.MACHINE_WORD_CTYPES = \
    char.MACHINE_WORD_CTYPES = {
        True: int,
        False: unsigned_int }

    unsigned_long = unsigned_int
    long = int

    signed_char = char
    signed_short = short
    signed_int = int
    signed_long = long
