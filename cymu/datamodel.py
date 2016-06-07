
class DataModelError(Exception):
    pass


class VarAccessError(DataModelError):
    pass


class AddressSpace(object):
    pass


class CObj(object):
    """
    All C objects are instances of this class
    """

    def __init__(self, ctype, adr_space):
        self.ctype = ctype
        self.adr_space = adr_space

    @property
    def initialized(self):
        return False

    val = property()


class BoundCType(object):

    def __init__(self, base_ctype, adr_space):
        self.adr_space = adr_space
        self.base_ctype = base_ctype

    def __call__(self, *args, **argv):
        return self.base_ctype(self.adr_space, *args, **argv)

    def __repr__(self):
        return '<bound ' + repr(self.base_ctype)[1:]

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

    def cast(self, cobj, adr_space=None):
        raise NotImplementedError()


class IntCObj(CObj):

    def __init__(self, ctype, adr_space, init_val=None):
        super(IntCObj, self).__init__(ctype, adr_space)
        self.__val = None
        if init_val is not None:
            self.val = init_val

    @property
    def initialized(self):
        return self.__val is not None

    def get_val(self):
        if self.initialized:
            return self.__val
        else:
            raise VarAccessError('value is not initialized')

    def set_val(self, new_value):
        ctype = self.ctype

        if isinstance(new_value, IntCObj):
            py_obj = new_value.__val
        elif isinstance(new_value, (int, long)):
            py_obj = new_value
        else:
            raise TypeError(
                '{!r} cannot be converted to object of class {!r}'
                .format(new_value, self))

        if ctype.signed:
            py_obj -= ctype.min()
            py_obj &= ((1 << ctype.bits) - 1)
            py_obj += ctype.min()
        else:
            py_obj &= ((1 << ctype.bits) - 1)

        # convert back long back to int if possible
        py_obj_as_int = int(py_obj)
        if py_obj_as_int == py_obj:
            py_obj = py_obj_as_int

        self.__val = py_obj

    val = property(get_val, set_val)

    def __repr__(self):
        if self.initialized:
            return '{}({!r})'.format(self.ctype.name, self.__val)
        else:
            return '{}()'.format(self.ctype.name)

    def __cmp__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        return cmp(self_casted.__val, other_casted.__val)

    def __nonzero__(self):
        return True if self.__val else False

    def __int__(self):
        if self.__val is None:
            raise VarAccessError('variable is not initialized')
        else:
            return self.__val

    def __sub__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        pyobj = self_casted.__val - other_casted.__val
        return self_casted.ctype(self.adr_space, pyobj)

    def __isub__(self, other):
        self.val = self - other
        return self

    def __rsub__(self, other):
        self_casted, other_casted = self.ctype.implicit_cast(self, other)
        return other_casted - self_casted


class IntCType(CType):

    COBJ_TYPE = IntCObj

    def __init__(self, name, bits, signed):
        super(IntCType, self).__init__(name)
        self.bits = bits
        self.signed = signed
        self.implicit_cast = None

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

    def cast(self, cobj, adr_space=None):
        if isinstance(cobj, IntCObj):
            if adr_space is None:
                adr_space = cobj.adr_space
            if cobj.ctype == self and cobj.adr_space == adr_space:
                return cobj
        return self(adr_space, int(cobj))

    @staticmethod
    def create_implicit_caster(int_ctype, uint_ctype, *other_ctypes):
        def implicit_cast(*cobjs):
            signed = True
            adr_space = None
            for cobj in cobjs:
                if isinstance(cobj, IntCObj):
                    signed &= cobj.ctype.signed
                    if adr_space is not None:
                        assert adr_space is cobj.adr_space
                    else:
                        adr_space = cobj.adr_space
            widened_ctype = int_ctype if signed else uint_ctype
            return [widened_ctype.cast(cobj, adr_space) for cobj in cobjs]
        return implicit_cast


class StructCObj(CObj):

    def __init__(self, ctype, adr_space, *args, **argv):
        super(StructCObj, self).__init__(ctype, adr_space)
        init_vals = dict(zip((nm for nm, ctype in ctype.fields), args))
        init_vals.update(argv)
        if len(init_vals) != len(args) + len(argv):
            raise TypeError('struct got multiple initialization values for '
                            'single field')
        for attr_name, attr_c_type in ctype.fields:
            if len(init_vals) > 0:
                field_cobj = attr_c_type(adr_space, init_vals.get(attr_name, 0))    ### use .zero instead of 0
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

    @property
    def initialized(self):
        return all(getattr(self, fname).initialized
                   for fname, ftype in self.ctype.fields)


class StructCType(CType):

    COBJ_TYPE = StructCObj

    def __init__(self, name, fields):
        super(StructCType, self).__init__(name)
        self.fields = fields


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        self.__adr_space__ = AddressSpace()
        self.global_vars()

    def global_vars(self):
        return

    def __repr__(self):
        return "<CProgram>"

    unsigned_long = IntCType('unsigned_long', bits=32, signed=False)
    long = IntCType('long', bits=32, signed=True)
    unsigned_int = IntCType('unsigned_int', bits=32, signed=False)
    int = IntCType('int', bits=32, signed=True)
    unsigned_short = IntCType('unsigned_short', bits=16, signed=False)
    short = IntCType('short', bits=16, signed=True)
    unsigned_char = IntCType('unsigned_char', bits=8, signed=False)
    char = IntCType('char', bits=8, signed=True)
    
    long.implicit_cast = unsigned_long.implicit_cast = \
    int.implicit_cast = unsigned_int.implicit_cast = \
    short.implicit_cast = unsigned_short.implicit_cast = \
    char.implicit_cast = unsigned_char.implicit_cast = \
        IntCType.create_implicit_caster(int, unsigned_int,
                                     long, unsigned_long,
                                     short, unsigned_short,
                                     char, unsigned_char)
