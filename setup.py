from setuptools import setup, find_packages
import os

version = '1.0'

setup(name='collective.ploneldapplugin',
      version=version,
      description="Better Plone LDAP PAS plugin with proper data types conversion",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        ],
      keywords='plone ldap',
      author='Vitaliy Podoba',
      author_email='vitaliypodoba@gmail.com',
      url='http://github.com/vipod/collective.ploneldapplugin',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'plone.app.ldap==1.2.1',
          'collective.monkeypatcher',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      setup_requires=["PasteScript"],
      paster_plugins=["ZopeSkel"],
      )
