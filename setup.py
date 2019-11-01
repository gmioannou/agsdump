try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Dump ArcGIS Service',
    'author': 'George Ioannou',
    'url': 'http://github.com/gmioannou/agsdump',
    'download_url': 'http://github.com/gmioannou/fginspect',
    'author_email': 'gmioannou@gmail.com',
    'version': '0.1',
    'install_requires': ['nose'],
    'packages': ['agsdump'],
    'scripts': [],
    'name': 'agsdump',
	'entry_points': {
	    'console_scripts': [
			'agsdump = agsdump.agsdump:main'
		]
	}
}

setup(**config)
