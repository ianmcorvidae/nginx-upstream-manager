#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import unittest
import subprocess
import os
import os.path

class OutputTestCase(unittest.TestCase):
    """Tests that the code produces correct results."""
    def setUp(self):
        if os.path.exists('config.yaml'):
            os.rename('config.yaml', 'config.yaml.bak')
        os.rename('config.yaml.sample', 'config.yaml')
        subprocess.check_output('python2 ./upstream_manager.py fancycluster generate', shell=True)
        if os.path.exists('.rotate-fancycluster'):
            os.remove('.rotate-fancycluster')

    def tearDown(self):
        subprocess.call('git checkout HEAD config.yaml.sample', shell=True)
        if os.path.exists('config.yaml.bak'):
            os.rename('config.yaml.bak', 'config.yaml')
        if os.path.exists('.rotate-fancycluster'):
            os.remove('.rotate-fancycluster')
        if os.path.exists('fancycluster.conf'):
            os.remove('fancycluster.conf')

    def test_rotate(self):
        """Test the rotate command"""
        rotate = subprocess.check_output('python2 ./upstream_manager.py fancycluster rotate', shell=True)
        self.assertEqual(rotate.strip(), '192.168.0.2')
        rotate = subprocess.check_output('python2 ./upstream_manager.py fancycluster rotate', shell=True)
        self.assertEqual(rotate.strip(), '192.168.0.3')
        rotate = subprocess.check_output('python2 ./upstream_manager.py fancycluster rotate', shell=True)
        self.assertEqual(rotate.strip(), 'Done')
        self.assertTrue(not os.path.exists('.rotate-fancycluster'))

    def test_generated(self):
        """Test the generation worked correctly"""
        self.assertTrue(os.path.exists('fancycluster.conf'))
        fh = open('fancycluster.conf')
        generated_data = fh.read()
        fh.close()
        fh = open('fancycluster.conf.sample')
        sample_data = fh.read()
        fh.close()
        self.assertEqual(generated_data, sample_data)
