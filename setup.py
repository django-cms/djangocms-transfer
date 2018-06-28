from setuptools import find_packages, setup

import djangocms_transfer


INSTALL_REQUIREMENTS = [
    'Django>=1.8,<2',
    'django-cms>=3.4.2',
]


setup(
    name='djangocms-transfer',
    packages=find_packages(),
    include_package_data=True,
    version=djangocms_transfer.__version__,
    description=djangocms_transfer.__doc__,
    long_description=open('README.rst').read(),
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Software Development'
    ],
    install_requires=INSTALL_REQUIREMENTS,
    author='Divio AG',
    author_email='info@divio.ch',
    url='http://github.com/divio/djangocms-transfer',
    license='BSD',
)
