#!/bin/bash
#
# below you have to specify the range of channel groups *plus one*
#$ -t 1-4
#$ -cwd
#$ -j y
#$ -S /bin/bash
#$ -o /home/battaglia/batch_out
# you have to change the line above by hand unfortunately

# WORKDIR=/peones/${HOST} # this doesn't work for some peones, probably because of misconfiguration
WORKDIR=/local # but this is equivalent 

# here, we assume that on the NAS the data is stored according to the convention 
# ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${DATASET}
# moreover, we assume that there is a "master" probe file at 
# ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${PROBEFILE}
# the probe file is used to determine which files we need to download to each node 
# if your layout differs, you must change the two rsync commands below
REMOTE_USER=fpbatta@tompouce.science.ru.nl
REMOTE_ORIGDIR=/volume1/homes/reichler/data
REMOTE_DESTDIR=/volume1/homes/fpbatta/dataTestRonny

EXPERIMENT=SocialPFC
ANIMAL=m0001
DATASET=2014-10-30_15-04-50
PROBEFILE=${ANIMAL}_16.prb
NODE=106
DURATION=10
DEFAULT_GROUP=1 # in case we're not running in a SGE task

# ---------- end parameters 


REMOTE_SHARE=${REMOTE_USER}:$REMOTE_ORIGDIR
REMOTE_DEST=${REMOTE_USER}:$REMOTE_DESTDIR
export PATH=/home/battaglia/anaconda3/bin::$PATH
echo 
HOST=`hostname`
echo host $HOST

echo workdir $WORKDIR
cd $WORKDIR
SHARE=$USER
OUTFILE=${JOB_NAME}.o${JOB_ID}.${SGE_TASK_ID}
echo outfile $OUTFILE
mkdir -p $SHARE
cd $SHARE

if [ -z $SGE_TASK_ID ] ; then
	GROUP=${DEFAULT_GROUP}
else
	GROUP=$(expr $SGE_TASK_ID - 1)
fi


rm -rf ${DATASET}
mkdir -p ${DATASET}
cd ${DATASET}

# get the data and convert them in the right format for klusta
echo ---------------------------- loading data --------------------------
rsync -avh  -e ssh ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${PROBEFILE} .

source activate ophys
get_needed_channels --node=$NODE $PROBEFILE ${GROUP} > chans.txt
rsync --files-from=chans.txt  -avh  -e ssh ${REMOTE_SHARE}/${EXPERIMENT}/${ANIMAL}/${DATASET} .

echo ---------------------------- convert format ------------------------
mkdir -p klusta${GROUP}
oio . -l ${PROBEFILE} --channel-groups ${GROUP} -S -n $NODE -D ${DURATION} -o klusta${GROUP}/raw.dat

# run klusta
echo ---------------------------- spike sort ----------------------------
source activate klusta

cd klusta${GROUP}
klusta *.prm

cp /home/battaglia/batch_out/${OUTFILE} klusta${GROUP} 

echo ---------------------------- store result --------------------------

cd .. 
ssh ${REMOTE_USER} mkdir -p ${REMOTE_DESTDIR}/${EXPERIMENT}/${ANIMAL}/${DATASET}
rsync -avh -e ssh klusta${GROUP} $REMOTE_DEST/${EXPERIMENT}/${ANIMAL}/${DATASET}/klusta${GROUP}