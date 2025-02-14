from solo.basic_files import mkdir
from solo.date import Hour, DateIncrement, date_sequence
from solo.stage import Stage
from solo.configuration import Configuration
from solo.nice_dict import NiceDict
from datetime import datetime, timedelta
import os
import shutil
from dateutil import parser
import ufsda
import logging
import glob
import numpy as np
from wxflow import YAMLFile, parse_yaml, parse_j2yaml

__all__ = ['atm_background', 'atm_obs', 'bias_obs', 'background', 'background_ens', 'fv3jedi', 'obs', 'berror', 'gdas_fix', 'gdas_single_cycle']

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')


def gdas_fix(input_fix_dir, working_dir, config):
    """
    gdas_fix(input_fix_dir, working_dir, config):
        Stage fix files needed by FV3-JEDI for GDAS analyses
        input_fix_dir - path to root fix file directory
        working_dir - path to where files should be linked to
        config - dict containing configuration
    """
    # create output directories
    ufsda.disk_utils.mkdir(config['fv3jedi_fieldmetadata_dir'])
    ufsda.disk_utils.mkdir(config['fv3jedi_fix_dir'])

    # error checking
    dohybvar = config['DOHYBVAR']
    case = config['CASE']
    case_enkf = config['CASE_ENS']
    case_anl = config['CASE_ANL']
    if dohybvar and not case_enkf == case_anl:
        raise ValueError(f"dohybvar is '{dohybvar}' but case_enkf= '{case_enkf}' does not equal case_anl= '{case_anl}'")

    # set layers
    layers = int(config['LEVS'])-1

    # figure out staticb source
    staticb_source = config.get('STATICB_TYPE', 'gsibec')
    case_berror = case if staticb_source in ['gsibec'] else case_anl
    ufsda.disk_utils.symlink(os.path.join(input_fix_dir, staticb_source, case_berror),
                             config['fv3jedi_staticb_dir'])

    # link akbk file
    ufsda.disk_utils.symlink(os.path.join(input_fix_dir, 'fv3jedi',
                                          'fv3files', f"akbk{layers}.nc4"),
                             os.path.join(config['fv3jedi_fix_dir'], 'akbk.nc4'))
    # link other fv3files
    ufsda.disk_utils.symlink(os.path.join(input_fix_dir, 'fv3jedi',
                                          'fv3files', 'fmsmpp.nml'),
                             os.path.join(config['fv3jedi_fix_dir'], 'fmsmpp.nml'))
    ufsda.disk_utils.symlink(os.path.join(input_fix_dir, 'fv3jedi',
                                          'fv3files', 'field_table_gfdl'),
                             os.path.join(config['fv3jedi_fix_dir'], 'field_table'))
    # link fieldmetadata
    # Note that the required data will be dependent on input file type (restart vs history, etc.)
    gdasapp_parm = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'parm'))
    ufsda.disk_utils.symlink(os.path.join(gdasapp_parm, 'io', 'fv3jedi_fieldmetadata_restart.yaml'),
                             os.path.join(config['fv3jedi_fieldmetadata_dir'], 'fv3jedi_fieldmetadata_restart.yaml'))
    # link CRTM coeff dir
    ufsda.disk_utils.symlink(os.path.join(input_fix_dir, 'crtm', '2.4.0'),
                             config['CRTM_COEFF_DIR'])


def soca_fix(config):
    """
    soca_fix(input_fix_dir, config):
        Stage fix files needed by SOCA for GDAS analyses
        input_fix_dir - path to root fix file directory
        working_dir - path to where files should be linked to
        config - dict containing configuration
    """

    # link static B bump files
    bump_archive = os.path.join(config['soca_input_fix_dir'], 'bkgerr', 'bump')
    bump_scratch = os.path.join(config['stage_dir'], 'bump')
    if os.path.isdir(bump_archive):
        # link archived bump files
        ufsda.disk_utils.symlink(bump_archive, bump_scratch)
    else:
        # create an empty bump directory
        ufsda.disk_utils.mkdir(bump_scratch)

    # link static sst B
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'godas_sst_bgerr.nc'),
                             os.path.join(config['stage_dir'], 'godas_sst_bgerr.nc'))

    # link Rossby Radius file
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'rossrad.dat'),
                             os.path.join(config['stage_dir'], 'rossrad.dat'))
    # link name lists
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'field_table'),
                             os.path.join(config['stage_dir'], 'field_table'))
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'diag_table'),
                             os.path.join(config['stage_dir'], 'diag_table'))
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'MOM_input'),
                             os.path.join(config['stage_dir'], 'MOM_input'))
    # link field metadata
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'fields_metadata.yaml'),
                             os.path.join(config['stage_dir'], 'fields_metadata.yaml'))

    # link ufo <---> soca name variable mapping
    ufsda.disk_utils.symlink(os.path.join(config['soca_input_fix_dir'], 'obsop_name_map.yaml'),
                             os.path.join(config['stage_dir'], 'obsop_name_map.yaml'))

    # INPUT
    ufsda.disk_utils.copytree(os.path.join(config['soca_input_fix_dir'], 'INPUT'),
                              os.path.join(config['stage_dir'], 'INPUT'))


def background(config):
    """
    Stage backgrounds and create analysis directory
    This involves:
    - ln RESTART to bkg_dir
    - mkdir anl
    """
    rst_dir = os.path.join(config['background_dir'], 'RESTART')
    jedi_bkg_dir = os.path.join(config['DATA'], 'bkg')
    jedi_anl_dir = os.path.join(config['DATA'], 'anl')
    try:
        os.symlink(rst_dir, jedi_bkg_dir)
    except FileExistsError:
        os.remove(jedi_bkg_dir)
        os.symlink(rst_dir, jedi_bkg_dir)
    mkdir(jedi_anl_dir)


def fv3jedi(config):
    """
    fv3jedi(config)
    stage fix files needed for FV3-JEDI
    such as akbk, fieldmetadata, fms namelist, etc.
    uses input config dictionary for paths
    """
    # create output directory
    mkdir(config['stage_dir'])
    # call solo.Stage
    path = os.path.dirname(config['fv3jedi_stage'])
    stage = Stage(path, config['stage_dir'], config['fv3jedi_stage_files'])


def static(stage_dir, static_source_dir, static_source_files):
    """
    stage_dir: dir destination to copy files in
    static_source_dir: source dir
    static_source_files: list of files to copy
    """

    # create output directory
    mkdir(stage_dir)
    # call solo.Stage
    path = os.path.dirname(static_source_dir)
    stage = Stage(path, stage_dir, static_source_files)


def berror(config):
    """
    Stage background error
    This involves:
    - ln StaticB to analysis/staticb
    """
    jedi_staticb_dir = os.path.join(config['COMOUT'], 'analysis', 'staticb')

    # ln StaticB to analysis/staticb
    try:
        os.symlink(config['staticb_dir'], jedi_staticb_dir)
    except FileExistsError:
        os.remove(jedi_staticb_dir)
        os.symlink(config['staticb_dir'], jedi_staticb_dir)


def background_ens(config):
    """
    Stage backgrounds and optionally create analysis directories
    This involves:
    - ln member RESTART to bkg_mem
    - optionally mkdir anl_mem
    """

    # set background directory keyword based on dohybvar
    bkgdir = 'ens'
    if not config['DOHYBVAR']:
        bkgdir = 'bkg'

    for imem in range(1, config['NMEM_ENS']+1):
        memchar = f"mem{imem:03d}"
        logging.info(f'Stage background_ens {memchar}')
        rst_dir = os.path.join(config['COMIN_GES_ENS'], memchar, 'atmos', 'RESTART')
        jedi_bkg_dir = os.path.join(config['DATA'], bkgdir)
        jedi_bkg_mem = os.path.join(config['DATA'], bkgdir, memchar)
        jedi_anl_mem = os.path.join(config['DATA'], 'anl', memchar)
        mkdir(jedi_bkg_dir)
        try:
            os.symlink(rst_dir, jedi_bkg_mem)
        except FileExistsError:
            os.remove(jedi_bkg_mem)
            os.symlink(rst_dir, jedi_bkg_mem)

        # do not create member analysis directories for dohybvar
        if not config['DOHYBVAR']:
            mkdir(jedi_anl_mem)
