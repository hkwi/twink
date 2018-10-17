import unittest
try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup

setup(name='twink',
        version='0.3',
        description='Openflow library',
	long_description=open("README.md").read(),
	long_description_content_type="text/markdown",
        author='Hiroaki Kawai',
        author_email='hiroaki.kawai@gmail.com',
        url='https://github.com/hkwi/twink/',
        packages=['twink','twink.ofp4','twink.ofp5'],
        test_suite="test",
)
