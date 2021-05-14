import pyFAI
from bluesky.simulators import summarize_plan
from bluesky_darkframes.sim import DiffractionDetector, Shutter
from pkg_resources import resource_filename

from xpdacq.beamtime import load_calibration_md, xpdacq_count
from xpdacq.plans import XrayBasicPlans, MultiDistPlans
from xpdacq.xpdacq_conf import xpd_configuration

PONI_FILE = resource_filename("xpdacq", "tests/Ni_poni_file.poni")


def test_BasicPlans(fake_devices, calib_data):
    shutter = Shutter(name="shutter")
    xbp = XrayBasicPlans(shutter, "open", "closed", None)
    summarize_plan(xbp.count([fake_devices.det1], 2))
    summarize_plan(xbp.grid_scan([fake_devices.det1], fake_devices.motor1, 2, 3, 2))
    summarize_plan(xbp.config_by_poni(calib_data, PONI_FILE))


def test_create_dark_frame_preprocessor():
    det = DiffractionDetector(name="det")
    shutter = Shutter(name="shutter")
    xbp = XrayBasicPlans(shutter, "open", "closed", None)
    dark_frame_preprocessor = xbp.create_dark_frame_preprocessor(detector=det, max_age=3600)
    summarize_plan(dark_frame_preprocessor(xbp.count([det], 2)))


def test_MultiDistPlans(fake_devices, calib_data, db):
    ai0 = pyFAI.AzimuthalIntegrator(dist=0)
    ai1 = pyFAI.AzimuthalIntegrator(dist=1)
    mdp = MultiDistPlans(fake_devices.motor1, 0, 1, db, fake_devices.motor2, calib_data, fake_devices.motor2)
    mdp.add_dist(0, "test0", ai0)
    mdp.add_dist(1, "test1", ai1)
    summarize_plan(mdp.count([fake_devices.det1], 2))


def test_xpdacq_count():
    det = DiffractionDetector(name="det")
    xpd_configuration["shutter"] = Shutter(name="fast shutter")
    calibration_md = load_calibration_md(PONI_FILE)
    print(calibration_md)
    plan = xpdacq_count([det], calibration_md=calibration_md)
    summarize_plan(plan)
