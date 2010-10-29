import sys
import logging

from AccessControl.Permissions import add_user_folders

from zope.i18nmessageid import MessageFactory

from Products.PluggableAuthService.PluggableAuthService import \
    registerMultiPlugin

messageFactory = MessageFactory('collective.ploneldapplugin')

logger = logging.getLogger('collective.ploneldapplugin')
def logException(msg, context=None):
    logger.exception(msg)
    if context is not None:
        error_log = getattr(context, 'error_log', None)
        if error_log is not None:
            error_log.raising(sys.exc_info())

from collective.ploneldapplugin.ldapplugin import EnhancedPloneLDAPMultiPlugin, \
    manage_addEnhancedPloneLDAPMultiPluginForm, \
    manage_addEnhancedPloneLDAPMultiPlugin

registerMultiPlugin(EnhancedPloneLDAPMultiPlugin.meta_type)

def initialize(context):
    """Initializer called when used as a Zope 2 product."""

    context.registerClass(
            EnhancedPloneLDAPMultiPlugin,
            permission=add_user_folders,
            constructors=(manage_addEnhancedPloneLDAPMultiPluginForm,
                manage_addEnhancedPloneLDAPMultiPlugin),
            icon="www/ldapmultiplugin.png",
            visibility=None)

#    import patches
