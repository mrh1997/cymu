class VarAccessError(Exception):
    pass


class CObject(object):
    """
    All C objects are instances of this class
    """

    PYTHON_TYPE = None

    def __init__(self, init_val=None):
        self.__val = None
        if init_val is not None:
            self.__val = self.convert(init_val)

    @property
    def initialized(self):
        return self.val is not None

    def get_val(self):
        return self.__val

    def set_val(self, new_value):
        if not isinstance(new_value, self.PYTHON_TYPE):
            raise TypeError('expected value of type {!r}'
                            .format(self.PYTHON_TYPE))
        self.__val = new_value

    val = property(get_val, set_val)

    @property
    def checked_val(self):
        if self.initialized:
            return self.__val
        else:
            raise VarAccessError('variable is not inititialized')

    def copy(self):
        return type(self)(self.val)

    @classmethod
    def convert(cls, value):
        if isinstance(value, cls.PYTHON_TYPE):
            return value
        elif isinstance(value, cls):
            return value.checked_val
        else:
            raise TypeError("cannot convert from type '{}' to type '{}'"
                            .format(type(value).__name__, cls.__name__))

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance[self]

    def __set__(self, instance, value):
        instance[self].val = self.convert(value)

    def __repr__(self):
        if self.initialized:
            return '{}({!r})'.format(type(self).__name__, self.val)
        else:
            return '{}()'.format(type(self).__name__)


class CInt(CObject):

    PYTHON_TYPE = int

    def __cmp__(self, value):
        return cmp(self.val, self.convert(value))

    def __nonzero__(self):
        return True if self.val else False

    def __isub__(self, other):
        self.val -= self.convert(other)
        return self

    def __sub__(self, other):
        return self.__class__(self.val - self.convert(other))

    def __rsub__(self, other):
        return self.__class__(self.convert(other) - self.val)


class CProgram(object):

    def __init__(self):
        super(CProgram, self).__init__()
        self.__global_insts__ = dict()
        for attrname in dir(self):
            if attrname != '__global_insts__':
                attr = getattr(type(self), attrname)
                if isinstance(attr, CObject):
                    self.__global_insts__[attr] = attr.copy()

    def __repr__(self):
        return "<CProgram>"

    def __getitem__(self, c_obj):
        return self.__global_insts__[c_obj]

    def __setitem__(self, c_obj, inst_c_obj):
        self.__global_insts__[c_obj] = inst_c_obj
