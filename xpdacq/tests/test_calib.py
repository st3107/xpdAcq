"""module to test run_calibration"""
import os
import yaml
import uuid
import time
import shutil
import unittest
import numpy as np
from pathlib import Path

from pyFAI.calibration import Calibration
from pyFAI.geometry import Geometry

from xpdacq.glbl import glbl
from xpdacq.xpdacq_conf import configure_device, xpd_configuration
from xpdacq.simulation import pe1c, db, shctl1, cs700
from xpdacq.calib import (_configure_calib_instance,
                          _save_and_attach_calib_param,
                          _collect_calib_img,
                          _calibration,
                          _timestampstr)
from xpdacq.utils import import_sample_info
from xpdacq.xpdacq import CustomizedRunEngine
from xpdacq.beamtimeSetup import _start_beamtime

from pkg_resources import resource_filename as rs_fn
rs_dir = rs_fn('xpdacq', '/')
pytest_dir = rs_fn('xpdacq', 'tests/')

class calibTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = glbl['base']
        self.home_dir = os.path.join(self.base_dir, 'xpdUser')
        self.config_dir = os.path.join(self.base_dir, 'xpdConfig')
        self.PI_name = 'Billinge '
        # must be 30000 for proper load of config yaml => don't change
        self.saf_num = 300000
        self.wavelength = 0.1812
        self.experimenters = [('van der Banerjee', 'S0ham', 1),
                              ('Terban ', ' Max', 2)]
        # make xpdUser dir. That is required for simulation
        os.makedirs(self.home_dir, exist_ok=True)
        self.bt = _start_beamtime(self.PI_name, self.saf_num,
                                  self.experimenters,
                                  wavelength=self.wavelength)
        xlf = '300000_sample.xlsx'
        src = os.path.join(os.path.dirname(__file__), xlf)
        shutil.copyfile(src, os.path.join(glbl['import_dir'], xlf))
        import_sample_info(self.saf_num, self.bt)
        glbl['shutter_control'] = True
        self.xrun = CustomizedRunEngine(self.bt)
        # set simulation objects
        configure_device(db=db, shutter=shctl1,
                         area_det=pe1c, temp_controller=cs700)
        # link mds
        self.xrun.subscribe('all', xpd_configuration['db'].mds.insert)
        # calib yaml 
        calib_fn = [fn for fn in os.listdir(pytest_dir) if
                fn.endswith('calib.yml')]
        assert len(calib_fn) == 1
        self.calib_yml_fn = os.path.join(pytest_dir, calib_fn[0])

    def tearDown(self):
        os.chdir(self.base_dir)
        if os.path.isdir(self.home_dir):
            shutil.rmtree(self.home_dir)
        if os.path.isdir(os.path.join(self.base_dir, 'xpdConfig')):
            shutil.rmtree(os.path.join(self.base_dir, 'xpdConfig'))
        if os.path.isdir(os.path.join(self.base_dir, 'pe2_data')):
            shutil.rmtree(os.path.join(self.base_dir, 'pe2_data'))

    def test_configure_calib(self):
        c = _configure_calib_instance(None, None, wavelength=None)
        # calibrant is None, which default to Ni
        assert c.calibrant.__repr__().split(' ')[0] == 'Ni24'  # no magic
        # wavelength is None, so it should get the value from bt
        assert c.wavelength == self.bt.wavelength * 10 ** (-10)
        # detector is None, which default to Perkin detector 
        assert c.detector.get_name() == 'Perkin detector'

        c2 = _configure_calib_instance(None, None, wavelength=999)
        # wavelength is given, so it should get customized value
        assert c2.wavelength == 999 * 10 ** (-10)

    def test_smoke_collect_calb_img(self):
        c = _configure_calib_instance(None, None, wavelength=None)
        calib_uid = '1234'
        glbl['detector_calibration_server_uid'] = calib_uid
        img = _collect_calib_img(5.0, True, c, self.xrun)
        h = xpd_configuration['db'][-1]

        # is information passed down?
        assert c.calibrant.__repr__().split(' ')[0] == h.start['sample_name']
        # is image shape as expected?
        assert img.shape == (5, 5)
        # is dark subtraction operated as expected?
        # since simulated pe1c always generate the same array, so
        # subtracted image should be zeors
        assert img.all() == np.zeros((5, 5)).all()

    def test_save_and_attach_calib_param(self):
        # reload yaml to produce pre-calib Calibration instance
        with open(self.calib_yml_fn) as f:
            calib_dict = yaml.load(f)
        calib_dict.pop('is_pytest') # special tag for testing
        c = Calibration()
        geo = Geometry()
        geo.setPyFAI(**calib_dict)
        c.geoRef = geo
        #c.ai.setPyFAI(**calib_dict)
        timestr = _timestampstr(time.time())
        _save_and_attach_calib_param(c, timestr)
        # test information attached to glbl
        calib_config_dict = glbl['calib_config_dict']
        assert calib_config_dict['file_name'] == c.basename
        for k, v in c.geoRef.getPyFAI().items():
            assert glbl['calib_config_dict'][k] == v
        # verify calib params are saved as expected
        local_f = open(os.path.join(glbl['config_base'],
                                    glbl['calib_config_name']))
        reload_dict = yaml.load(local_f)
        # time and file_name will definitely be different
        # as they both involve current timestamp. exclude them
        for k in ['time', 'file_name']:
            # use list to exhaust generator so pop are applied to both
            list(map(lambda x: x.pop(k), [reload_dict, calib_dict]))
        assert reload_dict == calib_dict
