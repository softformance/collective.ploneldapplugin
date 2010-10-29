from zope.interface import Interface, Attribute

from collective.ploneldapplugin import messageFactory as _


class ILDAPAttributeConverter(Interface):
    """LDAP Attribute Values Converter"""
    
    default = Attribute(_(u"Default value for empty ldap attribute."))
    attribute = Attribute(_(u"python_ldap package LDAP Attribute."))
    
    def __init__(attribute):
        """Sets attribute"""
        
    def fromLDAPValue(value, info):
        """Converts ldap attribute value to proper python type.
        
        (ldap name, zope name, type (lines|string))
        """
    
    def toLDAPValue(value, info):
        """Converts python value to proper ldap attribute string.
        
        info - tuple containing zope related vars:
        (ldap name, zope name, type (lines|string))
        """
