from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django_otp.admin import OTPAdminSite
from django_otp.plugins.otp_static.admin import StaticDeviceAdmin
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin
from django_otp.plugins.otp_totp.models import TOTPDevice

secure_admin_site=OTPAdminSite(OTPAdminSite.name)
secure_admin_site.site_header='Nossas Delícias — Central Administrativa'
secure_admin_site.site_title='Nossas Delícias'
secure_admin_site.index_title='Operação, catálogo e clientes'
secure_admin_site.register(User,UserAdmin)
secure_admin_site.register(Group,GroupAdmin)
secure_admin_site.register(TOTPDevice,TOTPDeviceAdmin)
secure_admin_site.register(StaticDevice,StaticDeviceAdmin)
