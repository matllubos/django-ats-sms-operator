from setuptools import find_packages, setup

from ats_sms_operator.version import get_version


setup(
    name='django-ats-sms-operator',
    version=get_version(),
    description="ATS SMS operator library.",
    keywords='django, sms receiver',
    author='Lubos Matl, Oskar Hollmann',
    author_email='matllubos@gmail.com, oskar@hollmann.me',
    url='https://github.com/druids/django-ats-sms-operator',
    license='LGPL',
    package_dir={'ats_sms_operator': 'ats_sms_operator'},
    include_package_data=True,
    packages=find_packages(),
    classifiers=[
        'Development Status :: 1 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU LESSER GENERAL PUBLIC LICENSE (LGPL)',
        'Natural Language :: Czech',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
    ],
    install_requires=[
        'django>=1.6',
        'beautifulsoup4>=4.4.0',
        'html5lib>=0.999999',
        'django-ipware>=1.0.0',
        'requests==2.9.0',
        'django-chamber>=0.1.22',
        'django-phonenumber-field==1.1.0',
    ],
    dependency_links=[
        'https://github.com/druids/django-chamber/tarball/0.1.22#egg=django-chamber-0.1.22',
    ],
    zip_safe=False,
)
