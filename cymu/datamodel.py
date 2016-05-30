

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

    PYTHON_TYPE = None

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
            raise VarAccessError('global variable is not inititialized')
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
        if isinstance(value, cls.PYTHON_TYPE):
            return value
        elif isinstance(value, cls):
            return value.checked_val
        else:
            raise TypeError("cannot convert from type '{}' to type '{}'"
                            .format(type(value).__name__, cls.__name__))

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


class CInt(CData):

    PYTHON_TYPE = int

    def __cmp__(self, value):
        return cmp(self.val, self.convert(value))

    def __nonzero__(self):
        return True if self.val else False

    def __isub__(self, other):
        self.val -= self.convert(other)
        return self

    def __sub__(self, other):
        result = self.__class__(self.val - self.convert(other))
        if self.instantiated:
            return result.create_instance(self.adr_space)
        else:
            return result

    def __rsub__(self, other):
        result = self.__class__(self.convert(other) - self.val)
        if self.instantiated:
            return result.create_instance(self.adr_space)
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

    int = CInt
