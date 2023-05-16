#! /usr/bin/env bash

set -x
bindir=$1
srcdir=$2

# Set g-w HOMEgfs
export HOMEgfs=$srcdir/../../ # TODO: HOMEgfs had to be hard-coded in config

# Set variables for ctest
export PSLOT=gdas_test
export EXPDIR=$bindir/test/atm/global-workflow/testrun/experiments/$PSLOT
export PDY=20210323
export cyc=18
export CDATE=${PDY}${cyc}
export ROTDIR=$bindir/test/atm/global-workflow/testrun/ROTDIRS/$PSLOT
export RUN=gdas
export CDUMP=gdas
export DATAROOT=$bindir/test/atm/global-workflow/testrun/RUNDIR
export COMIN_GES=${bindir}/test/atm/bkg
export pid=${pid:-$$}
export jobid=$pid
export COMROOT=$DATAROOT
export ACCOUNT=da-cpu
export COM_TOP=$ROTDIR

# Set GFS COM paths
source "${HOMEgfs}/ush/preamble.sh"
source "${HOMEgfs}/parm/config/gfs/config.com"

# Set python path for workflow utilities and tasks
pygwPATH="${HOMEgfs}/ush/python:${HOMEgfs}/ush/python/pygw/src"
PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}${pygwPATH}"
export PYTHONPATH

# Detemine machine from config.base
machine=$(echo `grep 'machine=' $EXPDIR/config.base | cut -d"=" -f2` | tr -d '"')

# Set date variables for previous cycle
GDATE=`date +%Y%m%d%H -d "${CDATE:0:8} ${CDATE:8:2} - 6 hours"`
gPDY=$(echo $GDATE | cut -c1-8)
gcyc=$(echo $GDATE | cut -c9-10)
GDUMP="gdas"

# Set file prefixes
gprefix=$GDUMP.t${gcyc}z
oprefix=$CDUMP.t${cyc}z

# Generate COM variables from templates
YMD=${PDY} HH=${cyc} generate_com -rx COM_OBS

RUN=${GDUMP} YMD=${gPDY} HH=${gcyc} generate_com -rx \
    COM_ATMOS_ANALYSIS_PREV:COM_ATMOS_ANALYSIS_TMPL \
    COM_ATMOS_HISTORY_PREV:COM_ATMOS_HISTORY_TMPL \
    COM_ATMOS_RESTART_PREV:COM_ATMOS_RESTART_TMPL

# Link radiance bias correction files
dpath=gdas.$gPDY/$gcyc/analysis/atmos
mkdir -p $COM_ATMOS_ANALYSIS_PREV
flist="amsua_n19.satbias.nc4 amsua_n19.satbias_cov.nc4 amsua_n19.tlapse.txt"
for file in $flist; do
   ln -fs $GDASAPP_TESTDATA/lowres/$dpath/$gprefix.$file $COM_ATMOS_ANALYSIS_PREV/
done

# Link atmospheric background on gaussian grid
dpath=gdas.$gPDY/$gcyc/model_data/atmos/history
mkdir -p $COM_ATMOS_HISTORY_PREV
flist="atmf006.nc"
for file in $flist; do
   ln -fs $GDASAPP_TESTDATA/lowres/$dpath/${gprefix}.${file} $COM_ATMOS_HISTORY_PREV/
done

# Link atmospheric bacgkround on tiles
dpath=gdas.$gPDY/$gcyc/model_data/atmos
COM_ATMOS_RESTART_PREV_DIRNAME=$(dirname $COM_ATMOS_RESTART_PREV)
mkdir -p $COM_ATMOS_RESTART_PREV_DIRNAME
flist="restart"
for file in $flist; do
   ln -fs $GDASAPP_TESTDATA/lowres/$dpath/$file $COM_ATMOS_RESTART_PREV_DIRNAME/
done

# Link observations
dpath=gdas.$PDY/$cyc/obs
mkdir -p $COM_OBS
flist="amsua_n19.$CDATE.nc4 sondes.$CDATE.nc4"
for file in $flist; do
   ln -fs $GDASAPP_TESTDATA/lowres/$dpath/${oprefix}.$file $COM_OBS/
done

# Execute j-job
if [ $machine != 'HERA' ]; then
    ${HOMEgfs}/jobs/JGLOBAL_ATM_ANALYSIS_INITIALIZE
else
    sbatch -n 1 --account=$ACCOUNT --qos=debug --time=00:10:00 --export=ALL --wait ${HOMEgfs}/jobs/JGLOBAL_ATM_ANALYSIS_INITIALIZE
fi