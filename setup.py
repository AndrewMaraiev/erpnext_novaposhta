# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

# get version from __version__ variable in erpnext_shipping/__init__.py
from erpnext_shipping import __version__ as version

setup(
	name='erpnext_novaposhta',
	version=version,
	description='A NP Shipping Integration for ERPNext',
	author='ikrok',
	author_email='maraiev.a@ikrok.net',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=['cowsay==5.0.0']
)
