import types
import time
from datetime import datetime, date
from ldap.schema.models import AttributeType

from DateTime import DateTime

from zope.interface import implements
from zope.component import adapts

from collective.ploneldapplugin.interfaces import ILDAPAttributeConverter

class BaseConverter(object):
    """Abstract converter class to perform some common routine"""
    
    implements(ILDAPAttributeConverter)
    adapts(AttributeType)
    
    def __init__(self, attribute):
        """Default implementation for LDAP attribute values converter
        
        Arguments:
          attribute - python ldap attribute holding ldap related info,
        """
        self.attribute = attribute    

class DefaultConverter(BaseConverter):
    """Makes sure everything going into ldap is a string."""
    
    default = u""
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        if isinstance(value, str):
            value = value.decode('utf-8')
        return value
    
    def toLDAPValue(self, value, info):
        """See interface"""
        if not value:
            value = ""
        elif not isinstance(value, types.StringTypes):
            value = unicode(value, 'utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        return value

class NullConverter(BaseConverter):
    """Converter to keep values from ldap as it is.
    
    Mostly usefull for LDAP internal attribute types as
    objectClass, dn, etc...
    """
    
    default = None

    def fromLDAPValue(self, value, info):
        """See interface"""
        return value
    
    def toLDAPValue(self, value, info):
        """See interface"""
        return value

class StringConverter(BaseConverter):
    """Mostly handles directoryString and similar syntaxes
    as utf-8 encoded strings.
    """
    
    default = u""
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        if isinstance(value, str):
            value = value.decode('utf-8')
        return value
    
    def toLDAPValue(self, value, info):
        """See interface"""
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        return value

class IntegerConverter(BaseConverter):
    """Handles ldap integer syntaxes"""
    
    default = 0
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        return int(value)
    
    def toLDAPValue(self, value, info):
        """See interface"""
        if not isinstance(value, str):
            value = str(value)
        return value

class NumericConverter(BaseConverter):
    """Handles ldap integer syntaxes"""
    
    default = 0.0
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        return float(value)
    
    def toLDAPValue(self, value, info):
        """See interface"""
        if not isinstance(value, str):
            value = str(value)
        return value

class BooleanConverter(BaseConverter):
    """Handles ldap boolean syntaxes"""
    
    default = False
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        return value == u'TRUE' and True or False
    
    def toLDAPValue(self, value, info):
        """See interface"""
        if value:
            value = 'TRUE'
        else:
            value = 'FALSE'
        return value

class DateTimeConverter(BaseConverter):
    """Handles ldap datetime syntaxes.
    
    Can handle both python datetime and zope DateTime
    objects into ldap direction. Not sure how to make smart
    choice between these datetimes in opposite direction.
    """
    
    default = None
    
    format = '%Y%m%d%H%M%SZ'
    
    def fromLDAPValue(self, value, info):
        """See interface"""
        # check that we return datetimes in instance timezone
        try:
            value = datetime(*time.strptime(value, self.format)[:6])
        except ValueError, e:
            return None
        # TODO: temporarily workaround for login time attribute
        #       we need a way to distinguish between python and
        #       zope datetime objects, when to return which one
        if info[1] == 'login_time':
            value = DateTime(value.isoformat())
        return value
    
    def toLDAPValue(self, value, info):
        """See interface.
        
        It's required to keep time attributes inside ldap in
        Universal timezones."""
        # TODO: make sure python datetime is saved in UTC timezone
        if isinstance(value, DateTime):
            value = value.toZone('UTC')
            value = "%0.4d%0.2d%0.2d%0.2d%0.2d%0.2dZ" % (
                value._year, value._month, value._day,
                value._hour, value._minute, value._second)
        elif isinstance(value, (datetime, date)):
            value = value.strftime(self.format)
        elif isinstance(value, time.struct_time):
            value = time.strftime(self.format, value)
        elif value is None:
            value = ''
        elif isinstance(value, unicode):
            value = value.encode('utf-8')
        elif not isinstance(value, str):
            value = str(value)
        return value
