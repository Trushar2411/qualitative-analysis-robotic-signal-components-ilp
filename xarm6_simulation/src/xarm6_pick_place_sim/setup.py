from glob import glob
from setuptools import setup

name = 'xarm6_pick_place_sim'
setup(
    name=name, version='0.1.4', packages=[name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + name]),
        ('share/' + name, ['package.xml']),
        ('share/' + name + '/launch', glob('launch/*.launch.py')),
        ('share/' + name + '/config', glob('config/*.yaml')),
        ('share/' + name + '/worlds', glob('worlds/*.world')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Project maintainer', maintainer_email='maintainer@example.com',
    description='xArm6 simulation, gripper recording and CSV export', license='MIT',
    entry_points={'console_scripts': [
        'run_sequence = xarm6_pick_place_sim.sequence:main',
        'export_bag = xarm6_pick_place_sim.export_bag:main',
    ]},
)
