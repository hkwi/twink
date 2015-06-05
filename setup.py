from distutils.core import setup

setup(name='twink',
        version='0.2',
        description='Openflow library',
        author='Hiroaki Kawai',
        author_email='hiroaki.kawai@gmail.com',
        url='https://github.com/hkwi/twink/',
        packages=['twink','twink.ofp4','twink.ofp5']
)
