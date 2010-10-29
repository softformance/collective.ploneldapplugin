import logging
from ldap import schema

from Acquisition import aq_base
from persistent.mapping import PersistentMapping

from Products.CMFCore.MemberDataTool import MemberData as BaseMemberData
from Products.PluggableAuthService.interfaces.authservice import \
    IPluggableAuthService
from Products.CMFPlone.MemberDataTool import _marker
from Products.PlonePAS.utils import getCharset

from collective.ploneldapplugin.ldapproperty import EnhancedLDAPPropertySheet
from collective.ploneldapplugin import logException

# below functions are methods copied from EnchancedPloneMultiPlugin class

def getLDAPAttrs(self):
    """Return LDAP Schema Attributes Mapping:
    
    {
      (ldapname, zopename, type): (Attribute, Syntax OID),
    }
    """
    # add attribute if needed
    if not hasattr(aq_base(self), '_ldapattrs'):
        self._ldapattrs = PersistentMapping()
    
    # fill it in if it's empty
    if not self._ldapattrs:
        acl = self._getLDAPUserFolder()
        meta = self._getLDAPMetaData(acl)
        if meta:
            for info in acl.getSchemaConfig().values():
                ldapname, zopename, type = (info['ldap_name'],
                    info['public_name'], info['multivalued'] and 'lines' or
                    'string')
                if not zopename or not meta.has_key(ldapname):
                    continue
                self._ldapattrs[(ldapname, zopename, type)] = meta[ldapname]
    
    return self._ldapattrs

def _getLDAPMetaData(self, acl):
    """Return ldap attributes metadata
    
    {
      ldapname: (attribute, syntax oid),
    }
    """
    try:
        connection = acl._delegate.connect()
        subentrydn = connection.search_subschemasubentry_s()
        entry = connection.read_subschemasubentry_s(subentrydn)
        subschema = schema.SubSchema(entry)
        must, may = subschema.attribute_types(acl._user_objclasses)
    except Exception, e:
        logException(u"Error while trying to gather LDAP Attributes Schema"
                     " Metadata", acl)
        return {}
    
    # gets attribute type syntax oid recursively if needed
    def _get_syntax_oid(attr, default=None):
        oid = attr.syntax
        if not oid:
            for sup in attr.sup:
                parent = subschema.get_inheritedobj(schema.AttributeType,
                    sup)
                oid = _get_syntax_oid(parent, default)
        return oid or default
    
    data = {}
    for attribute in must.values() + may.values():
        oid = _get_syntax_oid(attribute)            
        for name in attribute.names:
            data[name] = (attribute, oid)
    return data

def getPropertiesForUser(self, user, request=None):
    """Fullfill PropertiesPlugin requirements"""
    try:
        return EnhancedLDAPPropertySheet(self.id, user)
    except KeyError:
        return None

def setPropertiesForUser(self, user, propertysheet):
    """Use here propertysheet API thus avoiding code duplication"""
    propertysheet.setProperties(user, propertysheet._properties)

# patching
from Products.PloneLDAP.plugins.ldap import PloneLDAPMultiPlugin
PloneLDAPMultiPlugin.getLDAPAttrs = getLDAPAttrs
PloneLDAPMultiPlugin._getLDAPMetaData = _getLDAPMetaData
PloneLDAPMultiPlugin.getPropertiesForUser = getPropertiesForUser
PloneLDAPMultiPlugin.setPropertiesForUser = setPropertiesForUser

encoding = 'utf-8'

# encoding for LDAPUserFolder product
import Products.LDAPUserFolder.utils
Products.LDAPUserFolder.utils.encoding = encoding

def doAddUser(self , login , password):
    """We patch PloneLDAP doAddUser method to prevent setting 'unset' for
    all empty attributes.
    """
    acl = self._getLDAPUserFolder()

    if acl is None:
        return False

    attrs = {}
    attrs['dn'] = login
    attrs['user_pw'] = attrs['confirm_pw'] = password
    # For uid and loginname we assume that they are the same. This
    # need not be true, but PlonePAS treats them the same when creating
    # users.
    for key in (acl._uid_attr, acl._login_attr, acl._rdnattr):
        if key not in attrs:
            attrs[key] = login

    # vipod: this Evil is commented out in this patch
    # Evil: grab all schema attributes and fill them with a default
    # text. This is needed to be able to create LDAP entries where
    # attributes besides uid, login and rdn are required.
#        for (key,name) in acl.getLDAPSchema():
#            if key not in attrs:
#                attrs[key]="unset"

    res = acl.manage_addUser(kwargs=attrs)

    if res:
        logger.error('manage_addUser failed with %s' % res)

    view_name = self.getId() + '_enumerateUsers'
    self.ZCacheable_invalidate(view_name = view_name,)

    return not res

def addGroup(self, id, **kw):
    """Patch PloneLDAP plugin to return here True to avoid creating more than
    one group inside other Group Management plugins.
    """
    self.acl_users.manage_addGroup(id)
    return True

def getProperty(self, id, default=_marker):
    """Passes default value to property sheets"""
    sheets = None
    if not IPluggableAuthService.providedBy(self.acl_users):
        return BaseMemberData.getProperty(self, id)
    else:
        # It's a PAS! Whee!
        user = self.getUser()
        sheets = getattr(user, 'getOrderedPropertySheets', lambda: None)()

        # we won't always have PlonePAS users, due to acquisition,
        # nor are guaranteed property sheets
        if not sheets:
            return BaseMemberData.getProperty(self, id, default)

    charset = getCharset(self)

    # If we made this far, we found a PAS and some property sheets.
    for sheet in sheets:
        if sheet.hasProperty(id):
            # Return the first one that has the property.
            value = sheet.getProperty(id, default)
            if isinstance(value, unicode):
                # XXX Temporarily work around the fact that
                # property sheets blindly store and return
                # unicode. This is sub-optimal and should be
                # dealed with at the property sheets level by
                # using Zope's converters.
                return value.encode(charset)
            return value

    # Couldn't find the property in the property sheets. Try to
    # delegate back to the base implementation.
    return BaseMemberData.getProperty(self, id, default)
