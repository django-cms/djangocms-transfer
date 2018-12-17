from distutils.version import LooseVersion

import cms

cms_version = LooseVersion(cms.__version__)

LTE_CMS_3_4 = cms_version < LooseVersion('3.5')
LTE_CMS_3_5 = cms_version < LooseVersion('3.6')
GTE_CMS_3_6 = cms_version >= LooseVersion('3.6')
